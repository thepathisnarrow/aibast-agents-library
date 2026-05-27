"""
Enterprise Architect Agent — the lead architect on every demo build.

This agent owns end-to-end solution design for a demo. It applies the
Microsoft Azure Well-Architected Framework (WAF) pillars
(Reliability, Security, Cost Optimization, Operational Excellence,
Performance Efficiency) to the customer scenario and decides:

  - Where data should land (Fabric OneLake vs. Azure Storage vs. both)
  - Which Microsoft services are in scope
  - The hand-off plan to specialist architects:
        * Azure Architect    — RGs, networking, identity, storage
        * Fabric Architect   — workspaces, items, connections, governance
        * Purview Architect  — classification, DLP, sensitivity labels
  - Open questions that ONLY the Hub SE (Dave) can answer

When an open architectural question cannot be answered from the demo request
context, the orchestrator MUST surface it via `ask_user` AND post a comment
on the backing GitHub issue (handled at the runner layer). This agent's job is
to *identify* those questions and return them in a structured block so the
orchestrator can escalate cleanly.

This agent does NOT provision anything itself. It only designs and dispatches.
"""

import json
from agents.basic_agent import BasicAgent


WAF_PILLARS = [
    ("Reliability", "Resilience to failure, recovery, redundancy."),
    ("Security", "Identity, network isolation, encryption, secrets, RBAC."),
    ("Cost Optimization", "Right-sizing, capacity sharing, lifecycle."),
    ("Operational Excellence", "Observability, IaC, deployment automation."),
    ("Performance Efficiency", "Throughput, latency, capacity headroom."),
]

SUBORDINATE_ARCHITECTS = [
    ("azure_architect", "RGs, networking, identity, storage, compute. NEVER creates Fabric capacity or Purview."),
    ("fabric_architect", "Workspaces, lakehouses, warehouses, items, connections (uses EXISTING Fabric capacity)."),
    ("purview_architect", "Classifications, DLP, sensitivity labels, governance (uses EXISTING Purview account)."),
]


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/enterprise-architect",
    "version": "1.0.0",
    "display_name": "Enterprise Architect Agent",
    "description": (
        "WAF-aware lead architect. Designs end-to-end demo solutions, decides "
        "where data lands, coordinates Azure / Fabric / Purview architects, and "
        "flags open questions that must be escalated to the Hub SE."
    ),
    "tags": ["architect", "waf", "design", "orchestration"],
    "category": "architecture",
}


class EnterpriseArchitectAgent(BasicAgent):
    """Lead architect: designs the demo and delegates to specialist architects."""

    def __init__(self):
        self.name = "enterprise_architect"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["design", "list_pillars", "list_architects"],
                        "description": "design = produce the architecture for a demo; list_* = reference info.",
                    },
                    "demo": {
                        "type": "object",
                        "description": (
                            "The demo request payload. Expected keys: title, customer_name, "
                            "scenario, template, requirements[], technologies[], "
                            "customer_website_url, industry_primary, industry_secondary, "
                            "azure_region, existing_fabric_workspace_id."
                        ),
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "design")
        if action == "list_pillars":
            return "\n".join(f"- **{n}** — {d}" for n, d in WAF_PILLARS)
        if action == "list_architects":
            return "\n".join(f"- `{n}` — {d}" for n, d in SUBORDINATE_ARCHITECTS)
        if action == "design":
            return self._design(kwargs.get("demo") or {})
        return f"Unknown action: {action}"

    def _design(self, demo: dict) -> str:
        customer = demo.get("customer_name") or "(unspecified)"
        scenario = demo.get("scenario") or ""
        reqs = demo.get("requirements") or []
        techs = demo.get("technologies") or []
        website = demo.get("customer_website_url") or ""
        ind_primary = demo.get("industry_primary") or "(not specified)"
        ind_secondary = demo.get("industry_secondary") or ""
        region = demo.get("azure_region") or "westus3"
        existing_ws = demo.get("existing_fabric_workspace_id") or ""

        # Decide data landing zone based on requirements / technologies signal.
        wants_streaming = any("stream" in r.lower() or "real-time" in r.lower() for r in reqs) \
            or any("eventstream" in t.lower() or "event hub" in t.lower() or "real-time" in t.lower() for t in techs)
        wants_mirror = any("mirror" in t.lower() for t in techs) or any("mirror" in r.lower() for r in reqs)
        wants_governance = any("govern" in r.lower() or "compliance" in r.lower() for r in reqs) \
            or any("purview" in t.lower() for t in techs)
        wants_copilot = any("copilot" in r.lower() for r in reqs) or any("copilot" in t.lower() for t in techs)

        landing = self._decide_landing(reqs, techs)

        # Collect open questions that the orchestrator should escalate via ask_user.
        open_questions: list[str] = []
        if not scenario.strip():
            open_questions.append("The scenario field is empty. What is the core business problem this demo proves out?")
        if not ind_primary or ind_primary == "(not specified)":
            open_questions.append("No primary industry was selected. Which industry should the synthetic data and narrative reflect?")
        if not techs:
            open_questions.append("No technologies were chosen. Should this demo stay Fabric-only or also include Azure/M365 surfaces?")
        if wants_copilot and not website and not scenario.lower().count("teams"):
            open_questions.append("Copilot integration was requested — should the surface be Teams, M365 Copilot, or a custom Copilot Studio agent?")

        lines = [
            f"# Enterprise Architecture — {demo.get('title') or 'Untitled Demo'}",
            "",
            f"**Customer:** {customer}" + (f" (`{website}`)" if website else ""),
            f"**Industry:** {ind_primary}" + (f" / {ind_secondary}" if ind_secondary else ""),
            f"**Target Azure Region:** {region}",
        ]
        if existing_ws:
            lines.append(f"**Existing Fabric Workspace:** `{existing_ws}` (reuse — do not create new)")
        lines.append("")

        # Solution shape
        lines += [
            "## Solution Shape",
            f"- **Data landing:** {landing}",
            f"- **Streaming:** {'yes — Eventstream + KQL path' if wants_streaming else 'no — batch-only'}",
            f"- **Mirroring:** {'yes — zero-ETL from operational store(s)' if wants_mirror else 'no'}",
            f"- **Governance:** {'yes — Purview design required' if wants_governance else 'minimal (no Purview scope)'}",
            f"- **AI surface:** {'Copilot/Foundry agent' if wants_copilot else 'BI-only (Power BI / Direct Lake)'}",
            "",
        ]

        # WAF pillars
        lines += ["## WAF Pillar Notes"]
        lines += [
            "- **Reliability:** demo capacity already provisioned; no SLA work required.",
            "- **Security:** reuse MEA identity; all RBAC scoped to the new RG; no shared secrets in code.",
            f"- **Cost Optimization:** share the existing Fabric capacity; new Azure resources land in a single demo RG in `{region}` so cleanup is one command.",
            "- **Operational Excellence:** every step emits to the run transcript; rollback notes captured in the runbook.",
            "- **Performance Efficiency:** Direct Lake for BI; KQL for hot-path streaming; bounded sample data volumes.",
            "",
        ]

        # Hand-off plan
        lines += [
            "## Hand-off Plan (call these architects, in order)",
            "1. **`azure_architect`** — create the demo RG and any Azure-native resources required by the scenario (storage, Event Hubs, SQL, etc.).",
            f"   *Hard constraint:* MUST NOT create a new Fabric capacity or Purview account — both already exist in `{region}`.",
            "2. **`fabric_architect`** — design workspace layout (reuse `" + (existing_ws or "<new>") + "`), lakehouses/warehouses, connections, items.",
        ]
        if wants_governance:
            lines.append("3. **`purview_architect`** — design classifications, DLP, and sensitivity labels (uses the existing Purview account).")
        lines += [
            "",
            "After the architects align on the design, hand off to the **builder agents** (`data_engineer`, `fabric_mirroring`, `fabric_realtime_intelligence`, `semantic_model`, `fabric_data_agent_builder`, `copilot_studio_connector`, `foundry_agent_builder`, `m365_template_factory`) per the orchestrator's plan.",
            "",
        ]

        # Demo data
        lines += [
            "## Demo Data",
            f"Call **`demo_data`** with `customer_website_url='{website}'` and `industry_primary='{ind_primary}'`"
            + (f", `industry_secondary='{ind_secondary}'`" if ind_secondary else "")
            + ". If no public data is available, the agent will generate industry-appropriate synthetic data.",
            "",
        ]

        # Open questions block (machine-readable + human-readable)
        if open_questions:
            lines += [
                "## OPEN QUESTIONS — ESCALATE TO HUB SE",
                "The orchestrator MUST call `ask_user` for each of these before proceeding. "
                "Each `ask_user` call should also be mirrored to the backing GitHub issue as a comment.",
                "",
            ]
            for q in open_questions:
                lines.append(f"- {q}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps({"open_questions": open_questions}, indent=2))
            lines.append("```")
        else:
            lines.append("## OPEN QUESTIONS — none. Proceed.")

        return "\n".join(lines)

    def _decide_landing(self, reqs: list, techs: list) -> str:
        wants_realtime = any("stream" in r.lower() or "real-time" in r.lower() for r in reqs) \
            or any("real-time" in t.lower() or "eventstream" in t.lower() for t in techs)
        wants_warehouse = any("warehouse" in t.lower() or "sql" in t.lower() for t in techs)
        if wants_realtime and wants_warehouse:
            return "Hybrid — OneLake Lakehouse for batch + KQL Database for hot path + Warehouse for SQL workloads."
        if wants_realtime:
            return "Fabric Real-Time Intelligence — Eventstream → KQL Database → OneLake shortcut for analytics."
        if wants_warehouse:
            return "Fabric Warehouse (T-SQL) + Lakehouse — gold layer in Warehouse, raw/silver in Lakehouse."
        return "Fabric Lakehouse — OneLake (Delta) as the single landing zone. BI via Direct Lake."
