"""
agent_runner.py — Background worker that executes demo runs end-to-end.

A "run" is a single execution of a demo. The worker:
  1. Loads the demo's metadata (title, scenario, customer, requirements, tech)
  2. Drives a Copilot tool-calling loop with ALL specialist agents exposed as tools
     plus a special `ask_user` tool the model can call to pause and ask the user
     a clarifying question.
  3. Persists every message, tool call, tool result, and question as an
     append-only JSONL event log so the dashboard can stream the full
     conversation live.

Persistence layout:
  .brainstem_data/runs/index.json                — demo_id -> [run_id, ...]
  .brainstem_data/runs/{run_id}/run.json         — current state
  .brainstem_data/runs/{run_id}/events.jsonl     — append-only event stream

The worker thread is started by brainstem.py on app init.

Imports of brainstem (load_agents, call_copilot) are LAZY to avoid circular
imports at module load.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_RUNS_DIR = os.path.join(_BASE_DIR, ".brainstem_data", "runs")
_INDEX_FILE = os.path.join(_RUNS_DIR, "index.json")

os.makedirs(_RUNS_DIR, exist_ok=True)


# ── Constants ────────────────────────────────────────────────────────────────

# Max tool-call rounds per run (each round = 1 LLM call + N tool executions).
# Generous because a real demo may chain 8-12 specialist agents.
MAX_ROUNDS = 25

# How long the worker waits for the user to answer a question before giving up.
# 30 minutes — adjust as needed.
ANSWER_TIMEOUT_SEC = 30 * 60


# ── Run / event helpers ──────────────────────────────────────────────────────

_index_lock = threading.Lock()
_run_locks: dict[str, threading.Lock] = {}
_run_locks_guard = threading.Lock()


def _run_lock(run_id: str) -> threading.Lock:
    with _run_locks_guard:
        lock = _run_locks.get(run_id)
        if lock is None:
            lock = threading.Lock()
            _run_locks[run_id] = lock
        return lock


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_dir(run_id: str) -> str:
    d = os.path.join(_RUNS_DIR, run_id)
    os.makedirs(d, exist_ok=True)
    return d


def _run_state_path(run_id: str) -> str:
    return os.path.join(_run_dir(run_id), "run.json")


def _events_path(run_id: str) -> str:
    return os.path.join(_run_dir(run_id), "events.jsonl")


def _read_index() -> dict[str, list[str]]:
    if not os.path.exists(_INDEX_FILE):
        return {}
    try:
        with open(_INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_index(idx: dict[str, list[str]]) -> None:
    with open(_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2)


def _register_run(demo_id: str, run_id: str) -> None:
    with _index_lock:
        idx = _read_index()
        idx.setdefault(demo_id, []).insert(0, run_id)  # newest first
        _write_index(idx)


def get_runs_for_demo(demo_id: str) -> list[dict]:
    """Return run summaries for a demo, newest first."""
    idx = _read_index()
    out: list[dict] = []
    for rid in idx.get(demo_id, []):
        state = read_run_state(rid)
        if state:
            out.append(state)
    return out


def read_run_state(run_id: str) -> dict | None:
    path = _run_state_path(run_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_run_state(state: dict) -> None:
    state["updated_at"] = _now_iso()
    path = _run_state_path(state["run_id"])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def _patch_run_state(run_id: str, **changes) -> dict | None:
    with _run_lock(run_id):
        state = read_run_state(run_id)
        if state is None:
            return None
        state.update(changes)
        _write_run_state(state)
        return state


def read_events(run_id: str, since_seq: int = -1) -> list[dict]:
    """Return events with seq > since_seq (newest events appended last)."""
    path = _events_path(run_id)
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("seq", -1) > since_seq:
                    out.append(ev)
    except Exception as e:
        print(f"[runner] read_events error: {e}")
    return out


def _append_event(run_id: str, ev_type: str, data: dict) -> int:
    """Append an event and return its seq number. Also bumps event_count on state."""
    with _run_lock(run_id):
        state = read_run_state(run_id) or {}
        seq = int(state.get("event_count", 0))
        ev = {
            "seq": seq,
            "ts": _now_iso(),
            "type": ev_type,
            "data": data,
        }
        with open(_events_path(run_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
        state["event_count"] = seq + 1
        state["updated_at"] = _now_iso()
        _write_run_state(state)
        return seq


# ── Pending-question machinery ───────────────────────────────────────────────

# When the worker thread emits a question, it parks on an Event for that run.
# The HTTP /answer endpoint fills in the answer + sets the event.

_pending: dict[str, dict] = {}  # run_id -> { "question_id": str, "event": Event, "answer": str | None }
_pending_lock = threading.Lock()


def submit_answer(run_id: str, question_id: str, answer: str) -> bool:
    """Called by the HTTP layer when the user answers a pending question.
    Returns True if the answer was accepted (matching question was pending)."""
    with _pending_lock:
        slot = _pending.get(run_id)
        if not slot or slot.get("question_id") != question_id:
            return False
        slot["answer"] = answer
        slot["event"].set()
        return True


# ── Run creation + queue ─────────────────────────────────────────────────────

_run_queue: "queue.Queue[str]" = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def create_run(demo: dict) -> dict:
    """Create a new run for a demo and enqueue it. Returns the run state."""
    run_id = uuid.uuid4().hex[:12]
    state = {
        "run_id": run_id,
        "demo_id": str(demo.get("id", "")),
        "demo_title": demo.get("title", "(untitled)"),
        "customer_name": demo.get("customer_name") or "",
        "customer_website_url": demo.get("customer_website_url") or "",
        "industry_primary": demo.get("industry_primary") or "",
        "industry_secondary": demo.get("industry_secondary") or "",
        "azure_region": demo.get("azure_region") or "westus3",
        "existing_fabric_workspace_id": demo.get("existing_fabric_workspace_id") or "",
        "scenario": demo.get("scenario") or demo.get("description") or "",
        "template": demo.get("template") or "",
        "requirements": demo.get("requirements") or [],
        "technologies": demo.get("technologies") or [],
        "status": "queued",
        "pending_question": None,
        "started_at": None,
        "updated_at": _now_iso(),
        "completed_at": None,
        "summary": None,
        "error": None,
        "event_count": 0,
    }
    _write_run_state(state)
    _register_run(state["demo_id"], run_id)
    _append_event(run_id, "run_queued", {"demo_id": state["demo_id"], "demo_title": state["demo_title"]})
    _run_queue.put(run_id)
    _ensure_worker()
    return state


def cancel_run(run_id: str) -> bool:
    state = read_run_state(run_id)
    if not state or state.get("status") in ("completed", "failed", "cancelled"):
        return False
    _patch_run_state(run_id, status="cancelled", completed_at=_now_iso())
    _append_event(run_id, "run_cancelled", {})
    # If a question was pending, unblock the worker with a synthetic answer.
    with _pending_lock:
        slot = _pending.get(run_id)
        if slot:
            slot["answer"] = "__CANCELLED__"
            slot["event"].set()
    return True


# ── The worker ───────────────────────────────────────────────────────────────

def _ensure_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(target=_worker_loop, name="brainstem-runner", daemon=True)
        t.start()
        _worker_started = True
        print("[runner] background worker started")


def _worker_loop() -> None:
    while True:
        try:
            run_id = _run_queue.get()
        except Exception:
            time.sleep(1)
            continue
        try:
            _execute_run(run_id)
        except Exception as e:
            traceback.print_exc()
            _patch_run_state(run_id, status="failed", error=str(e), completed_at=_now_iso())
            _append_event(run_id, "run_failed", {"error": str(e)})


def _execute_run(run_id: str) -> None:
    state = read_run_state(run_id)
    if not state:
        return
    if state.get("status") == "cancelled":
        return

    _patch_run_state(run_id, status="running", started_at=_now_iso())
    _append_event(run_id, "run_started", {})

    # Lazy import to avoid cycles
    from brainstem import load_agents, call_copilot, load_soul

    try:
        agents = load_agents()
        soul = load_soul()
    except Exception as e:
        raise RuntimeError(f"Failed to load agents/soul: {e}") from e

    # Build tool list: all specialist agents + ask_user
    tools = [a.to_tool() for a in agents.values()]
    tools.append({
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "Pause the run and ask Dave (the user) a clarifying question. "
                "Use this when you genuinely cannot proceed without input — "
                "e.g. ambiguous requirements, missing customer detail, or a "
                "decision only the human can make (which region? which tenant? "
                "should we use mirroring or pipelines?). The user's answer will "
                "come back as the tool result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user. Be specific.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional brief context on why you need this answer.",
                    },
                },
                "required": ["question"],
            },
        },
    })
    tools.append({
        "type": "function",
        "function": {
            "name": "finish_run",
            "description": (
                "Call this when the demo plan is complete (or you've hit an "
                "unrecoverable blocker after using ask_user). Provide a final "
                "markdown summary of what was accomplished, links to created "
                "resources, and any open items."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Markdown summary of the run's outcome.",
                    },
                    "outcome": {
                        "type": "string",
                        "enum": ["completed", "blocked"],
                        "description": "completed = ran the demo end-to-end; blocked = could not finish.",
                    },
                },
                "required": ["summary", "outcome"],
            },
        },
    })

    # Build the seed conversation
    system_content = soul + "\n\n" + _runner_system_addendum(state)
    user_prompt = _build_initial_prompt(state)

    messages: list[dict] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]

    _append_event(run_id, "llm_message", {"role": "user", "content": user_prompt})

    for round_idx in range(MAX_ROUNDS):
        # Check for cancellation between rounds
        cur = read_run_state(run_id)
        if not cur or cur.get("status") == "cancelled":
            return

        _append_event(run_id, "round_started", {"round": round_idx + 1})

        try:
            response = call_copilot(messages, tools=tools)
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}") from e

        choice = (response.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        finish = choice.get("finish_reason", "")

        # Normalize: ensure dict shape (some clients return objects)
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": msg.get("content"),
        }
        if msg.get("tool_calls"):
            assistant_msg["tool_calls"] = msg["tool_calls"]

        messages.append(assistant_msg)

        if assistant_msg.get("content"):
            _append_event(run_id, "llm_message", {
                "role": "assistant",
                "content": assistant_msg["content"],
                "finish_reason": finish,
            })

        tool_calls = assistant_msg.get("tool_calls") or []
        if not tool_calls:
            # Model returned a plain response with no tool calls → treat as finish.
            summary = assistant_msg.get("content") or "(no summary)"
            _finish(run_id, "completed", summary)
            return

        # Execute each tool call, emitting events
        finish_requested = False
        for tc in tool_calls:
            fn = (tc.get("function") or {})
            name = fn.get("name") or "?"
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except Exception:
                args = {}
            tc_id = tc.get("id") or uuid.uuid4().hex[:8]

            _append_event(run_id, "tool_call", {
                "tool_call_id": tc_id,
                "name": name,
                "arguments": args,
            })

            # ── Special tool: ask_user ───────────────────────────────────
            if name == "ask_user":
                answer = _ask_user_and_wait(run_id, args.get("question", ""), args.get("context", ""))
                messages.append({
                    "tool_call_id": tc_id,
                    "role": "tool",
                    "name": name,
                    "content": answer,
                })
                continue

            # ── Special tool: finish_run ─────────────────────────────────
            if name == "finish_run":
                outcome = args.get("outcome") or "completed"
                summary = args.get("summary") or "(no summary)"
                messages.append({
                    "tool_call_id": tc_id,
                    "role": "tool",
                    "name": name,
                    "content": "ack",
                })
                status = "completed" if outcome == "completed" else "failed"
                _finish(run_id, status, summary)
                finish_requested = True
                break

            # ── Regular agent tool ───────────────────────────────────────
            agent = agents.get(name)
            if not agent:
                err = f"Agent '{name}' not found."
                _append_event(run_id, "tool_result", {
                    "tool_call_id": tc_id, "name": name, "ok": False, "result": err,
                })
                messages.append({
                    "tool_call_id": tc_id, "role": "tool", "name": name, "content": err,
                })
                continue

            try:
                result = agent.perform(**args)
                result_str = str(result)
                _append_event(run_id, "tool_result", {
                    "tool_call_id": tc_id, "name": name, "ok": True,
                    "result": result_str,
                })
                messages.append({
                    "tool_call_id": tc_id, "role": "tool", "name": name,
                    "content": result_str,
                })
            except Exception as e:
                err = f"Agent error: {e}"
                _append_event(run_id, "tool_result", {
                    "tool_call_id": tc_id, "name": name, "ok": False, "result": err,
                })
                messages.append({
                    "tool_call_id": tc_id, "role": "tool", "name": name, "content": err,
                })

        if finish_requested:
            return

    # Hit the round cap without finishing
    _finish(run_id, "failed", f"Run exceeded max rounds ({MAX_ROUNDS}) without calling finish_run.")


def _ask_user_and_wait(run_id: str, question: str, context: str) -> str:
    """Emit a question event, park on an Event, return the user's answer string."""
    question_id = uuid.uuid4().hex[:8]
    ev = threading.Event()
    with _pending_lock:
        _pending[run_id] = {"question_id": question_id, "event": ev, "answer": None}

    _append_event(run_id, "question", {
        "question_id": question_id,
        "question": question,
        "context": context,
    })
    _patch_run_state(
        run_id,
        status="awaiting_user",
        pending_question={
            "question_id": question_id,
            "question": question,
            "context": context,
            "asked_at": _now_iso(),
        },
    )

    # Best-effort: also post a comment to the GitHub demo issue so the SE
    # sees the question outside the dashboard (mobile, email notifications).
    try:
        state = read_run_state(run_id) or {}
        demo_id = state.get("demo_id")
        if demo_id:
            from dashboard_api import _comment_on_demo  # lazy import to avoid cycle
            ctx_line = f"\n\n_Context: {context}_" if context else ""
            _comment_on_demo(
                demo_id,
                f"\u2753 Build paused \u2014 question for SE:\n\n> {question}{ctx_line}\n\nAnswer via the Brainstem dashboard.",
            )
    except Exception as _e:
        print(f"[runner] GH comment for ask_user failed (non-fatal): {_e}")

    got = ev.wait(timeout=ANSWER_TIMEOUT_SEC)

    with _pending_lock:
        slot = _pending.pop(run_id, None)
    answer = (slot or {}).get("answer") if got else None

    if not got:
        _append_event(run_id, "answer", {
            "question_id": question_id,
            "answer": "(timed out — no answer received)",
            "timed_out": True,
        })
        _patch_run_state(run_id, status="running", pending_question=None)
        return "(The user did not answer in time. Make a sensible default assumption, note it in your summary, and continue.)"

    if answer == "__CANCELLED__":
        # _execute_run will see cancelled status on next iteration
        return "(Run cancelled by user.)"

    _append_event(run_id, "answer", {
        "question_id": question_id,
        "answer": answer,
    })
    _patch_run_state(run_id, status="running", pending_question=None)
    return answer or ""


def _finish(run_id: str, status: str, summary: str) -> None:
    _patch_run_state(
        run_id,
        status=status,
        summary=summary,
        completed_at=_now_iso(),
        pending_question=None,
    )
    _append_event(run_id, "run_completed" if status == "completed" else "run_failed", {
        "status": status,
        "summary": summary,
    })


# ── Prompt construction ──────────────────────────────────────────────────────

def _runner_system_addendum(state: dict) -> str:
    return (
        "You are running in AUTONOMOUS EXECUTION mode to BUILD a demo (not run one). "
        "Specialist agents available as tools: enterprise_architect, azure_architect, "
        "fabric_architect, purview_architect, demo_data, data_engineer, fabric_admin, "
        "purview_data_governance, purview_data_security, purview_risk_compliance, "
        "semantic_model, copilot_studio_connector, foundry_agent_builder, "
        "demo_orchestrator (advisor), etc.\n\n"
        "Required workflow:\n"
        "  1. Call `enterprise_architect` action='design' first to produce a WAF-aligned "
        "architecture spanning Azure / Fabric / Purview. It will choose the data "
        "landing pattern (Lakehouse / Warehouse / Eventhouse / hybrid).\n"
        "  2. Call `demo_data` action='source' to source or generate industry-appropriate "
        "sample data for the customer's primary industry.\n"
        "  3. Hand off implementation pieces to: `azure_architect` (cloud resources), "
        "`fabric_architect` (workspace + items), `purview_architect` (governance), "
        "then execute via the specialist build agents (data_engineer, fabric_admin, etc.).\n"
        "  4. Use `ask_user` ONLY for genuine blockers (ambiguous requirement, judgment "
        "call, missing credential). Each ask_user call will also post a comment to the "
        "GitHub demo issue automatically, so phrase questions clearly for the SE.\n"
        "  5. When done (or blocked), call `finish_run` with a markdown summary.\n\n"
        "Hard constraints:\n"
        "  - NEVER create a new Fabric capacity. Reuse the existing one in westus3.\n"
        "  - NEVER create a new Purview account. Reuse the existing one.\n"
        "  - NEVER delete or destroy anything without explicit user approval via ask_user.\n"
        "  - Respect SAFETY_CONSTRAINTS in basic_agent.py."
    )


def _build_initial_prompt(state: dict) -> str:
    parts = [
        f"# Demo Build Request",
        f"**Demo ID:** {state['demo_id']}",
        f"**Title:** {state['demo_title']}",
        f"**Customer:** {state.get('customer_name') or '(unspecified)'}",
    ]
    if state.get("customer_website_url"):
        parts.append(f"**Customer Website:** {state['customer_website_url']}")
    industry_line = state.get("industry_primary") or "(unspecified)"
    if state.get("industry_secondary"):
        industry_line += f" / {state['industry_secondary']}"
    parts.append(f"**Industry:** {industry_line}")
    parts.append(f"**Azure Region:** {state.get('azure_region') or 'westus3'}")
    if state.get("existing_fabric_workspace_id"):
        parts.append(f"**Existing Fabric Workspace:** `{state['existing_fabric_workspace_id']}`")
    if state.get("template"):
        parts.append(f"**Template:** {state['template']}")
    if state.get("scenario"):
        parts.append(f"\n## Scenario\n{state['scenario']}")
    if state.get("requirements"):
        parts.append("\n## Requirements\n" + "\n".join(f"- {r}" for r in state["requirements"]))
    if state.get("technologies"):
        parts.append("\n## Technologies\n" + "\n".join(f"- {t}" for t in state["technologies"]))
    parts.append(
        "\n---\n"
        "Begin by calling `enterprise_architect` action='design' to produce the "
        "architecture, then `demo_data` to source data, then execute via the "
        "specialist agents. Stream your thinking \u2014 every assistant message "
        "will be shown to the user in real time on the dashboard."
    )
    return "\n".join(parts)
