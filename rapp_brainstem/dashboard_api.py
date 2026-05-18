"""
Dashboard API — backend endpoints for the Brainstem Dashboard.

Provides /api/dashboard/overview (aggregated data from all sources)
and /api/dashboard/projects (GitHub Issues CRUD).

Data sources:
  - Agents: Loaded agent modules from agents/ directory
  - Azure: ARM API via MEA credential (resource groups, resources, cost)
  - Fabric: Fabric REST API via MEA credential (capacities, workspaces, items)
  - Purview: Purview Data Map API via MEA credential (assets, policies)
  - Projects: GitHub Issues in microsoft/aibast-agents-library
"""

import os
import time
import json
import glob
import traceback
import importlib.util

import requests
from flask import Blueprint, jsonify, request

# ── Blueprint ─────────────────────────────────────────────────────────────────

dashboard_bp = Blueprint("dashboard", __name__)

# ── Configuration ─────────────────────────────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENTS_PATH = os.path.join(_BASE_DIR, "agents")

# Cache: avoid hitting APIs more than once per 30s
_cache = {"data": None, "timestamp": 0}
_CACHE_TTL = 25  # seconds (slightly less than frontend 30s poll)

# GitHub config for project queue
_GH_REPO = "microsoft/aibast-agents-library"


# ── Helpers: Azure credential ─────────────────────────────────────────────────

def _get_azure_token(scope: str) -> str | None:
    """Get an Azure token via AzureCliCredential for MEA identity."""
    try:
        from azure.identity import AzureCliCredential
        # Load tenant from auth_config
        import sys
        if _AGENTS_PATH not in sys.path:
            sys.path.insert(0, _AGENTS_PATH)
        from auth_config import TARGET_M365_TENANT, SCOPES
        tenant_id = TARGET_M365_TENANT["tenant_id"]
        resource_scope = SCOPES.get(scope, scope)
        credential = AzureCliCredential(tenant_id=tenant_id)
        return credential.get_token(resource_scope).token
    except Exception as e:
        print(f"[dashboard] Azure token error ({scope}): {e}")
        return None


def _get_subscription_id() -> str:
    """Get subscription ID from auth_config."""
    try:
        import sys
        if _AGENTS_PATH not in sys.path:
            sys.path.insert(0, _AGENTS_PATH)
        from auth_config import TARGET_M365_TENANT
        return TARGET_M365_TENANT["subscription_id"]
    except Exception:
        return ""


def _get_github_token() -> str | None:
    """Get GitHub token for Issues API. Uses gh CLI."""
    try:
        import subprocess, sys
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
            shell=(sys.platform == "win32"),
        )
        token = result.stdout.strip()
        return token if token else None
    except Exception:
        return None


# ── Data Fetchers ─────────────────────────────────────────────────────────────

def _fetch_agents() -> list[dict]:
    """List agents loaded from agents/ directory (lightweight — just name + description)."""
    agents = []
    pattern = os.path.join(_AGENTS_PATH, "*_agent.py")
    for filepath in glob.glob(pattern):
        basename = os.path.basename(filepath)
        # Derive a display name from file
        name = basename.replace("_agent.py", "").replace("_", " ").title()
        # Try to extract description from docstring (first line)
        desc = ""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read(2000)
            # Look for class docstring or module docstring
            if '"""' in content:
                start = content.index('"""') + 3
                end = content.index('"""', start)
                desc = content[start:end].strip().split("\n")[0]
        except Exception:
            pass
        agents.append({"name": name, "description": desc, "status": "ready"})
    return agents


def _fetch_projects() -> list[dict]:
    """Fetch open issues from GitHub repo as project queue."""
    token = _get_github_token()
    if not token:
        return []
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{_GH_REPO}/issues",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            params={"state": "open", "per_page": 20},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"[dashboard] GitHub issues error: {resp.status_code}")
            return []
        issues = resp.json()
        return [
            {
                "id": str(issue["number"]),
                "title": issue["title"],
                "description": (issue.get("body") or "")[:200],
                "status": _issue_status(issue),
                "created_at": issue["created_at"],
                "labels": [l["name"] for l in issue.get("labels", [])],
                "url": issue["html_url"],
            }
            for issue in issues
            if not issue.get("pull_request")  # exclude PRs
        ]
    except Exception as e:
        print(f"[dashboard] GitHub fetch error: {e}")
        return []


def _issue_status(issue: dict) -> str:
    """Map GitHub issue labels to project status."""
    labels = [l["name"].lower() for l in issue.get("labels", [])]
    if "in-progress" in labels or "in progress" in labels:
        return "in-progress"
    if "completed" in labels or "done" in labels:
        return "completed"
    return "queued"


def _fetch_azure() -> dict:
    """Fetch Azure resource groups, resources, and cost."""
    token = _get_azure_token("azure_management")
    sub_id = _get_subscription_id()
    result = {"resourceGroups": [], "totalResources": 0, "cost": {"actual": 0, "forecast": 0, "currency": "USD"}}

    if not token or not sub_id:
        return result

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Resource groups
    try:
        resp = requests.get(
            f"https://management.azure.com/subscriptions/{sub_id}/resourcegroups?api-version=2022-09-01",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            rgs = resp.json().get("value", [])
            total_resources = 0
            for rg in rgs:
                rg_name = rg["name"]
                # Get resources in this RG
                res_resp = requests.get(
                    f"https://management.azure.com/subscriptions/{sub_id}/resourceGroups/{rg_name}/resources?api-version=2022-09-01",
                    headers=headers,
                    timeout=10,
                )
                resources = []
                if res_resp.status_code == 200:
                    for r in res_resp.json().get("value", []):
                        resources.append({
                            "name": r["name"],
                            "type": r["type"],
                            "location": r.get("location", ""),
                        })
                total_resources += len(resources)
                result["resourceGroups"].append({
                    "name": rg_name,
                    "location": rg.get("location", ""),
                    "resources": resources,
                })
            result["totalResources"] = total_resources
    except Exception as e:
        print(f"[dashboard] Azure RG fetch error: {e}")

    # Cost Management (current billing period)
    try:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        start_of_month = now.replace(day=1).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")

        cost_resp = requests.post(
            f"https://management.azure.com/subscriptions/{sub_id}/providers/Microsoft.CostManagement/query?api-version=2023-03-01",
            headers=headers,
            json={
                "type": "ActualCost",
                "timeframe": "Custom",
                "timePeriod": {"from": start_of_month, "to": today},
                "dataset": {
                    "granularity": "None",
                    "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                },
            },
            timeout=15,
        )
        if cost_resp.status_code == 200:
            rows = cost_resp.json().get("properties", {}).get("rows", [])
            if rows:
                result["cost"]["actual"] = round(rows[0][0], 2)
                result["cost"]["currency"] = rows[0][1] if len(rows[0]) > 1 else "USD"

        # Forecast
        end_of_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        forecast_resp = requests.post(
            f"https://management.azure.com/subscriptions/{sub_id}/providers/Microsoft.CostManagement/forecast?api-version=2023-03-01",
            headers=headers,
            json={
                "type": "ActualCost",
                "timeframe": "Custom",
                "timePeriod": {"from": start_of_month, "to": end_of_month.strftime("%Y-%m-%d")},
                "dataset": {
                    "granularity": "None",
                    "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                },
            },
            timeout=15,
        )
        if forecast_resp.status_code == 200:
            rows = forecast_resp.json().get("properties", {}).get("rows", [])
            if rows:
                result["cost"]["forecast"] = round(sum(r[0] for r in rows), 2)
    except Exception as e:
        print(f"[dashboard] Azure cost fetch error: {e}")

    return result


def _fetch_fabric() -> dict:
    """Fetch Fabric capacities and workspaces."""
    token = _get_azure_token("fabric")
    result = {"capacities": [], "workspaces": []}

    if not token:
        return result

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Capacities (via Azure ARM)
    arm_token = _get_azure_token("azure_management")
    sub_id = _get_subscription_id()
    if arm_token and sub_id:
        try:
            resp = requests.get(
                f"https://management.azure.com/subscriptions/{sub_id}/providers/Microsoft.Fabric/capacities?api-version=2023-11-01",
                headers={"Authorization": f"Bearer {arm_token}", "Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code == 200:
                for cap in resp.json().get("value", []):
                    result["capacities"].append({
                        "id": cap.get("properties", {}).get("capacityId", cap.get("id", "")),
                        "name": cap["name"],
                        "state": cap.get("properties", {}).get("state", "Unknown"),
                        "sku": cap.get("sku", {}).get("name", ""),
                        "region": cap.get("location", ""),
                    })
        except Exception as e:
            print(f"[dashboard] Fabric capacity fetch error: {e}")

    # Workspaces (via Fabric API)
    try:
        resp = requests.get(
            "https://api.fabric.microsoft.com/v1/workspaces",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            for ws in resp.json().get("value", []):
                ws_data = {
                    "id": ws["id"],
                    "name": ws["displayName"],
                    "capacityId": ws.get("capacityId", ""),
                    "type": ws.get("type", "Workspace"),
                }
                # Fetch items for each workspace (limit to avoid slowness)
                try:
                    items_resp = requests.get(
                        f"https://api.fabric.microsoft.com/v1/workspaces/{ws['id']}/items",
                        headers=headers,
                        timeout=8,
                    )
                    if items_resp.status_code == 200:
                        ws_data["items"] = [
                            {"id": it["id"], "displayName": it["displayName"], "type": it["type"]}
                            for it in items_resp.json().get("value", [])[:50]
                        ]
                except Exception:
                    ws_data["items"] = []
                result["workspaces"].append(ws_data)
    except Exception as e:
        print(f"[dashboard] Fabric workspace fetch error: {e}")

    return result


def _fetch_purview() -> dict:
    """Fetch Purview data catalog assets and policies."""
    token = _get_azure_token("purview")
    result = {"assets": {"count": 0, "byType": {}}, "policies": {"count": 0}}

    if not token:
        return result

    # Purview Data Map — search for all assets
    # Use the tenant's Purview account endpoint
    import sys
    if _AGENTS_PATH not in sys.path:
        sys.path.insert(0, _AGENTS_PATH)
    try:
        from auth_config import TARGET_M365_TENANT
        tenant_domain = TARGET_M365_TENANT["tenant_id"]
        # Purview account name is typically the tenant prefix
        account_prefix = tenant_domain.split(".")[0].lower()
        purview_endpoint = f"https://{account_prefix}.purview.azure.com"
    except Exception:
        purview_endpoint = "https://purview.azure.com"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Search assets
    try:
        resp = requests.post(
            f"{purview_endpoint}/datamap/api/search/query?api-version=2023-09-01",
            headers=headers,
            json={"keywords": "*", "limit": 1},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            result["assets"]["count"] = data.get("@search.count", 0)
            # Get type facets
            facet_resp = requests.post(
                f"{purview_endpoint}/datamap/api/search/query?api-version=2023-09-01",
                headers=headers,
                json={
                    "keywords": "*",
                    "limit": 1,
                    "facets": [{"facet": "entityType", "count": 20}],
                },
                timeout=10,
            )
            if facet_resp.status_code == 200:
                facets = facet_resp.json().get("@search.facets", {}).get("entityType", [])
                result["assets"]["byType"] = {f["value"]: f["count"] for f in facets}
    except Exception as e:
        print(f"[dashboard] Purview asset fetch error: {e}")

    # Policies count
    try:
        pol_resp = requests.get(
            f"{purview_endpoint}/policystore/metadataPolicies?api-version=2021-07-01",
            headers=headers,
            timeout=10,
        )
        if pol_resp.status_code == 200:
            policies = pol_resp.json().get("values", [])
            result["policies"]["count"] = len(policies)
    except Exception as e:
        print(f"[dashboard] Purview policy fetch error: {e}")

    return result


# ── Main aggregator ───────────────────────────────────────────────────────────

def _build_dashboard_data() -> dict:
    """Build full dashboard data payload. Uses cache if fresh."""
    global _cache
    now = time.time()
    if _cache["data"] and (now - _cache["timestamp"]) < _CACHE_TTL:
        return _cache["data"]

    print("[dashboard] Refreshing dashboard data...")
    t0 = time.time()

    agents = _fetch_agents()
    projects = _fetch_projects()
    azure = _fetch_azure()
    fabric = _fetch_fabric()
    purview = _fetch_purview()

    data = {
        "agents": {"loaded": agents, "projects": projects},
        "azure": azure,
        "fabric": fabric,
        "purview": purview,
        "timestamp": now,
    }

    elapsed = time.time() - t0
    print(f"[dashboard] Data refresh complete in {elapsed:.1f}s")

    _cache = {"data": data, "timestamp": now}
    return data


# ── Routes ────────────────────────────────────────────────────────────────────

@dashboard_bp.route("/api/dashboard/overview", methods=["GET"])
def dashboard_overview():
    """Return aggregated dashboard data from all sources."""
    try:
        data = _build_dashboard_data()
        return jsonify(data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/dashboard/projects", methods=["GET"])
def dashboard_projects():
    """Return project queue (GitHub Issues)."""
    try:
        projects = _fetch_projects()
        return jsonify({"projects": projects})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/dashboard/projects", methods=["POST"])
def dashboard_create_project():
    """Create a new project (GitHub Issue) with optional file attachments."""
    token = _get_github_token()
    if not token:
        return jsonify({"error": "GitHub authentication required"}), 401

    # Support both JSON and FormData
    if request.content_type and "multipart/form-data" in request.content_type:
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        # Note: GitHub Issues API doesn't support file attachments directly.
        # Files would need to be uploaded separately or linked.
        # For now we note attached filenames in the issue body.
        files = request.files.getlist("files")
        if files:
            description += "\n\n---\n**Attached files:**\n"
            for f in files:
                description += f"- {f.filename}\n"
    else:
        data = request.get_json(force=True) or {}
        title = data.get("title", "").strip()
        description = data.get("description", "").strip()

    if not title:
        return jsonify({"error": "Title is required"}), 400

    try:
        resp = requests.post(
            f"https://api.github.com/repos/{_GH_REPO}/issues",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"title": title, "body": description, "labels": ["project"]},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            issue = resp.json()
            # Invalidate cache so next poll shows the new project
            _cache["timestamp"] = 0
            return jsonify({
                "id": str(issue["number"]),
                "title": issue["title"],
                "url": issue["html_url"],
            }), 201
        else:
            return jsonify({"error": f"GitHub API error: {resp.status_code}", "detail": resp.text[:300]}), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
