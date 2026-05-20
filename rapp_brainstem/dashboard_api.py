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


# Credential cache for secondary tenants (avoid re-creating per call)
_secondary_credentials: dict = {}


def _get_secondary_token(tenant_key: str, scope: str) -> str | None:
    """Get an Azure token for a secondary tenant via InteractiveBrowserCredential.

    Uses persistent token cache — first call opens browser, subsequent calls
    use the cached refresh token silently.
    """
    try:
        from azure.identity import InteractiveBrowserCredential, TokenCachePersistenceOptions
        import sys
        if _AGENTS_PATH not in sys.path:
            sys.path.insert(0, _AGENTS_PATH)
        from auth_config import SECONDARY_TENANTS, SCOPES

        tenant_cfg = SECONDARY_TENANTS.get(tenant_key)
        if not tenant_cfg or not tenant_cfg.get("tenant_id"):
            return None

        resource_scope = SCOPES.get(scope, scope)

        # Reuse cached credential instance
        if tenant_key not in _secondary_credentials:
            _secondary_credentials[tenant_key] = InteractiveBrowserCredential(
                tenant_id=tenant_cfg["tenant_id"],
                login_hint=tenant_cfg.get("login_hint", ""),
                cache_persistence_options=TokenCachePersistenceOptions(name=f"brainstem_{tenant_key}"),
            )

        credential = _secondary_credentials[tenant_key]
        return credential.get_token(resource_scope).token
    except Exception as e:
        print(f"[dashboard] Secondary token error ({tenant_key}/{scope}): {e}")
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


def _fetch_demos() -> list[dict]:
    """Fetch open demo requests from GitHub repo (issues with 'demo' label)."""
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
            params={"state": "all", "labels": "demo", "per_page": 30},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"[dashboard] GitHub demo issues error: {resp.status_code}")
            return []
        issues = resp.json()
        demos = []
        for issue in issues:
            if issue.get("pull_request"):
                continue
            # Parse metadata from issue body (JSON block)
            meta = _parse_demo_metadata(issue.get("body") or "")
            labels = [l["name"].lower() for l in issue.get("labels", [])]
            status = "completed" if issue["state"] == "closed" else _issue_status(issue)
            if status == "queued" and "draft" in labels:
                status = "draft"
            demos.append({
                "id": str(issue["number"]),
                "title": issue["title"],
                "customer_name": meta.get("customer_name", ""),
                "scenario": meta.get("scenario", ""),
                "template": meta.get("template", ""),
                "requirements": meta.get("requirements", []),
                "technologies": meta.get("technologies", []),
                "status": status,
                "assigned_agents": meta.get("assigned_agents", []),
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "url": issue["html_url"],
            })
        return demos
    except Exception as e:
        print(f"[dashboard] GitHub demo fetch error: {e}")
        return []


def _parse_demo_metadata(body: str) -> dict:
    """Extract JSON metadata block from issue body (fenced with ```json ... ```)."""
    meta = {}
    try:
        if "```json" in body:
            start = body.index("```json") + 7
            end = body.index("```", start)
            meta = json.loads(body[start:end])
    except (ValueError, json.JSONDecodeError):
        pass
    return meta


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
                "timeframe": "MonthToDate",
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
    """Fetch Fabric capacities and workspaces from primary + secondary tenants."""
    token = _get_azure_token("fabric")
    result = {"capacities": [], "workspaces": []}

    if not token:
        return result

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Capacities (via Azure ARM) — primary tenant only (has admin access)
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
                        "resourceId": cap.get("id", ""),
                        "name": cap["name"],
                        "state": cap.get("properties", {}).get("state", "Unknown"),
                        "sku": cap.get("sku", {}).get("name", ""),
                        "region": cap.get("location", ""),
                        "tenant": "primary",
                        "adminAccess": True,
                    })
        except Exception as e:
            print(f"[dashboard] Fabric capacity fetch error: {e}")

    # Workspaces (via Fabric API) — primary tenant
    try:
        resp = requests.get(
            "https://api.fabric.microsoft.com/v1/workspaces",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            for ws in resp.json().get("value", []):
                # Skip the default personal workspace
                if ws.get("displayName", "").lower() == "my workspace":
                    continue
                ws_data = {
                    "id": ws["id"],
                    "name": ws["displayName"],
                    "capacityId": ws.get("capacityId", ""),
                    "type": ws.get("type", "Workspace"),
                    "tenant": "primary",
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

    # ── Secondary tenants: Fabric workspaces + capacities (read-only) ──────
    import sys
    if _AGENTS_PATH not in sys.path:
        sys.path.insert(0, _AGENTS_PATH)
    try:
        from auth_config import SECONDARY_TENANTS
    except ImportError:
        SECONDARY_TENANTS = {}

    for tenant_key, tenant_cfg in SECONDARY_TENANTS.items():
        # Skip service status fetch for non-admin tenants
        if not tenant_cfg.get("admin_access", False):
            continue

        sec_fabric_token = _get_secondary_token(tenant_key, "fabric")
        if not sec_fabric_token:
            continue

        sec_headers = {"Authorization": f"Bearer {sec_fabric_token}", "Content-Type": "application/json"}

        # Secondary capacities (ARM) — only if subscription configured
        sec_sub_id = tenant_cfg.get("subscription_id", "")
        if sec_sub_id and tenant_cfg.get("admin_access", False):
            sec_arm_token = _get_secondary_token(tenant_key, "azure_management")
            if sec_arm_token:
                try:
                    resp = requests.get(
                        f"https://management.azure.com/subscriptions/{sec_sub_id}/providers/Microsoft.Fabric/capacities?api-version=2023-11-01",
                        headers={"Authorization": f"Bearer {sec_arm_token}", "Content-Type": "application/json"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        for cap in resp.json().get("value", []):
                            result["capacities"].append({
                                "id": cap.get("properties", {}).get("capacityId", cap.get("id", "")),
                                "resourceId": cap.get("id", ""),
                                "name": cap["name"],
                                "state": cap.get("properties", {}).get("state", "Unknown"),
                                "sku": cap.get("sku", {}).get("name", ""),
                                "region": cap.get("location", ""),
                                "tenant": tenant_key,
                                "adminAccess": tenant_cfg.get("admin_access", False),
                            })
                except Exception as e:
                    print(f"[dashboard] Secondary Fabric capacity error ({tenant_key}): {e}")

        # Secondary workspaces (Fabric API)
        try:
            resp = requests.get(
                "https://api.fabric.microsoft.com/v1/workspaces",
                headers=sec_headers,
                timeout=10,
            )
            if resp.status_code == 200:
                for ws in resp.json().get("value", []):
                    if ws.get("displayName", "").lower() == "my workspace":
                        continue
                    ws_data = {
                        "id": ws["id"],
                        "name": ws["displayName"],
                        "capacityId": ws.get("capacityId", ""),
                        "type": ws.get("type", "Workspace"),
                        "tenant": tenant_key,
                    }
                    try:
                        items_resp = requests.get(
                            f"https://api.fabric.microsoft.com/v1/workspaces/{ws['id']}/items",
                            headers=sec_headers,
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
            print(f"[dashboard] Secondary Fabric workspace error ({tenant_key}): {e}")

    return result


def _fetch_purview() -> dict:
    """Fetch Purview data catalog assets and policies from primary + secondary tenants."""
    token = _get_azure_token("purview")
    result = {"assets": {"count": 0, "byType": {}}, "policies": {"count": 0}, "tenants": {}}

    # Purview Data Map — search for all assets
    # Use the tenant's Purview account endpoint
    import sys
    if _AGENTS_PATH not in sys.path:
        sys.path.insert(0, _AGENTS_PATH)
    try:
        from auth_config import TARGET_M365_TENANT, SECONDARY_TENANTS
        tenant_domain = TARGET_M365_TENANT["tenant_id"]
        # Purview account name is typically the tenant prefix
        account_prefix = tenant_domain.split(".")[0].lower()
        purview_endpoint = f"https://{account_prefix}.purview.azure.com"
    except Exception:
        purview_endpoint = "https://purview.azure.com"
        SECONDARY_TENANTS = {}

    def _query_purview(endpoint: str, headers: dict, tenant_label: str) -> dict:
        """Query a Purview endpoint and return asset/policy counts."""
        tenant_data = {"assets": {"count": 0, "byType": {}}, "policies": {"count": 0}}
        # Search assets
        try:
            resp = requests.post(
                f"{endpoint}/datamap/api/search/query?api-version=2023-09-01",
                headers=headers,
                json={"keywords": "*", "limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                tenant_data["assets"]["count"] = data.get("@search.count", 0)
                # Get type facets
                facet_resp = requests.post(
                    f"{endpoint}/datamap/api/search/query?api-version=2023-09-01",
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
                    tenant_data["assets"]["byType"] = {f["value"]: f["count"] for f in facets}
        except Exception as e:
            print(f"[dashboard] Purview asset fetch error ({tenant_label}): {e}")

        # Policies count
        try:
            pol_resp = requests.get(
                f"{endpoint}/policystore/metadataPolicies?api-version=2021-07-01",
                headers=headers,
                timeout=10,
            )
            if pol_resp.status_code == 200:
                policies = pol_resp.json().get("values", [])
                tenant_data["policies"]["count"] = len(policies)
        except Exception as e:
            print(f"[dashboard] Purview policy fetch error ({tenant_label}): {e}")

        return tenant_data

    # ── Primary tenant ──────────────────────────────────────────────────────
    if token:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        primary_data = _query_purview(purview_endpoint, headers, "primary")
        result["assets"] = primary_data["assets"]
        result["policies"] = primary_data["policies"]
        result["tenants"]["primary"] = primary_data

    # ── Secondary tenants ───────────────────────────────────────────────────
    for tenant_key, tenant_cfg in SECONDARY_TENANTS.items():
        # Skip service status fetch for non-admin tenants
        if not tenant_cfg.get("admin_access", False):
            continue

        sec_token = _get_secondary_token(tenant_key, "purview")
        if not sec_token:
            continue

        sec_headers = {"Authorization": f"Bearer {sec_token}", "Content-Type": "application/json"}

        # Determine Purview endpoint for secondary
        sec_purview_account = tenant_cfg.get("purview_account", "")
        if sec_purview_account:
            sec_endpoint = f"https://{sec_purview_account}.purview.azure.com"
        else:
            # Derive from tenant_id (fallback)
            sec_endpoint = f"https://{tenant_cfg['tenant_id'].split('.')[0].lower() if '.' in tenant_cfg.get('tenant_id','') else tenant_cfg.get('tenant_id','')}.purview.azure.com"

        sec_data = _query_purview(sec_endpoint, sec_headers, tenant_key)
        result["tenants"][tenant_key] = sec_data

        # Aggregate into top-level counts
        result["assets"]["count"] += sec_data["assets"]["count"]
        for asset_type, count in sec_data["assets"].get("byType", {}).items():
            result["assets"]["byType"][asset_type] = result["assets"]["byType"].get(asset_type, 0) + count
        result["policies"]["count"] += sec_data["policies"]["count"]

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
    demos = _fetch_demos()

    data = {
        "agents": {"loaded": agents, "projects": projects},
        "azure": azure,
        "fabric": fabric,
        "purview": purview,
        "demos": demos,
        "timestamp": now,
    }

    elapsed = time.time() - t0
    print(f"[dashboard] Data refresh complete in {elapsed:.1f}s")

    _cache = {"data": data, "timestamp": now}
    return data


# ── Routes ────────────────────────────────────────────────────────────────────

@dashboard_bp.route("/api/dashboard/auth", methods=["GET"])
def dashboard_auth():
    """Return configured authentication accounts (no secrets). Reads fresh from env.yaml."""
    import yaml as _yaml

    env_yaml_path = os.path.join(_BASE_DIR, "env.yaml")
    if not os.path.exists(env_yaml_path):
        return jsonify({"accounts": []})

    with open(env_yaml_path, "r", encoding="utf-8") as f:
        cfg = _yaml.safe_load(f) or {}

    tenant_cfg = cfg.get("tenant", {})
    accounts = []

    # Primary account
    domain = tenant_cfg.get("domain", "")
    accounts.append({
        "key": "primary",
        "username": tenant_cfg.get("mea_admin", ""),
        "domain": domain,
        "displayName": tenant_cfg.get("display_name", "Primary"),
        "adminAccess": tenant_cfg.get("admin_access", True),
        "isPrimary": True,
    })

    # Secondary accounts
    for key, sec_cfg in (cfg.get("secondary_tenants") or {}).items():
        if not isinstance(sec_cfg, dict):
            continue
        accounts.append({
            "key": key,
            "username": sec_cfg.get("login_hint", ""),
            "domain": sec_cfg.get("tenant_id", ""),
            "displayName": sec_cfg.get("display_name", key),
            "adminAccess": sec_cfg.get("admin_access", False),
            "isPrimary": False,
        })
    return jsonify({"accounts": accounts})


@dashboard_bp.route("/api/dashboard/auth", methods=["PUT"])
def dashboard_auth_save():
    """Save authentication accounts to env.yaml."""
    import yaml

    payload = request.get_json(force=True)
    accounts = payload.get("accounts", [])

    env_yaml_path = os.path.join(_BASE_DIR, "env.yaml")
    if not os.path.exists(env_yaml_path):
        return jsonify({"error": "env.yaml not found"}), 404

    with open(env_yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # Separate primary vs secondary (use isPrimary boolean toggle)
    primary = next((a for a in accounts if a.get("isPrimary") is True), None)
    secondaries = [a for a in accounts if a.get("isPrimary") is not True]

    # Update primary tenant fields
    if primary:
        if "tenant" not in cfg:
            cfg["tenant"] = {}
        cfg["tenant"]["domain"] = primary.get("domain", "")
        cfg["tenant"]["mea_admin"] = primary.get("username", "")
        cfg["tenant"]["display_name"] = primary.get("displayName", "Primary")
        cfg["tenant"]["admin_access"] = primary.get("adminAccess", True)

    # Rebuild secondary_tenants section
    sec_dict = {}
    for acc in secondaries:
        key = acc.get("key", "").strip()
        if not key:
            continue
        sec_dict[key] = {
            "tenant_id": acc.get("domain", ""),
            "login_hint": acc.get("username", ""),
            "display_name": acc.get("displayName", key),
            "subscription_id": acc.get("subscriptionId", ""),
            "purview_account": acc.get("purviewAccount", ""),
            "admin_access": acc.get("adminAccess", False),
        }
    cfg["secondary_tenants"] = sec_dict

    with open(env_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

    return jsonify({"ok": True, "saved": len(accounts)})


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


@dashboard_bp.route("/api/dashboard/fabric/capacity/<action>", methods=["POST"])
def dashboard_fabric_capacity_action(action):
    """Resume or suspend a Fabric capacity. Polls until complete."""
    if action not in ("resume", "suspend"):
        return jsonify({"error": "Invalid action. Use 'resume' or 'suspend'."}), 400

    data = request.get_json(force=True) or {}
    resource_id = data.get("resourceId", "").strip()
    tenant_key = data.get("tenant", "primary")
    if not resource_id:
        return jsonify({"error": "resourceId is required"}), 400

    # Only allow actions on tenants with admin access
    if tenant_key != "primary":
        import sys
        if _AGENTS_PATH not in sys.path:
            sys.path.insert(0, _AGENTS_PATH)
        try:
            from auth_config import SECONDARY_TENANTS
            tenant_cfg = SECONDARY_TENANTS.get(tenant_key, {})
            if not tenant_cfg.get("admin_access", False):
                return jsonify({"status": "error", "action": action, "message": f"No admin access on tenant '{tenant_key}'"}), 200
        except ImportError:
            return jsonify({"status": "error", "action": action, "message": "Secondary tenant not configured"}), 200

    arm_token = _get_azure_token("azure_management") if tenant_key == "primary" else _get_secondary_token(tenant_key, "azure_management")
    if not arm_token:
        return jsonify({"error": "Unable to obtain ARM token"}), 500

    try:
        resp = requests.post(
            f"https://management.azure.com{resource_id}/{action}?api-version=2023-11-01",
            headers={"Authorization": f"Bearer {arm_token}", "Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code in (200, 202):
            # Poll for completion using Location or Azure-AsyncOperation header
            poll_url = resp.headers.get("Location") or resp.headers.get("Azure-AsyncOperation")
            if poll_url and resp.status_code == 202:
                import time as _time
                for _ in range(30):  # max ~60s polling
                    _time.sleep(2)
                    poll_resp = requests.get(
                        poll_url,
                        headers={"Authorization": f"Bearer {arm_token}"},
                        timeout=15,
                    )
                    if poll_resp.status_code == 200:
                        body = poll_resp.json() if poll_resp.text else {}
                        status = body.get("status", "Succeeded")
                        if status in ("Succeeded", "Completed"):
                            _cache["timestamp"] = 0
                            return jsonify({"status": "succeeded", "action": action}), 200
                        elif status in ("Failed", "Canceled"):
                            _cache["timestamp"] = 0
                            return jsonify({"status": "error", "action": action, "message": body.get("error", {}).get("message", f"Operation {status}")}), 200
                    elif poll_resp.status_code >= 400:
                        _cache["timestamp"] = 0
                        return jsonify({"status": "error", "action": action, "message": f"Poll returned {poll_resp.status_code}"}), 200
                # Timeout polling — treat as warning
                _cache["timestamp"] = 0
                return jsonify({"status": "warning", "action": action, "message": "Operation accepted but status unknown after 60s"}), 200
            # No poll URL or immediate 200 — treat as success
            _cache["timestamp"] = 0
            return jsonify({"status": "succeeded", "action": action}), 200
        else:
            return jsonify({"status": "error", "action": action, "message": f"ARM API error: {resp.status_code} — {resp.text[:200]}"}), 200
    except Exception as e:
        return jsonify({"status": "error", "action": action, "message": str(e)}), 200


@dashboard_bp.route("/api/dashboard/demos", methods=["GET"])
def dashboard_demos():
    """Return demo requests (GitHub Issues with 'demo' label)."""
    try:
        demos = _fetch_demos()
        return jsonify(demos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/dashboard/demos", methods=["POST"])
def dashboard_create_demo():
    """Create a new demo request as a GitHub Issue with metadata JSON block."""
    token = _get_github_token()
    if not token:
        return jsonify({"error": "GitHub authentication required"}), 401

    # Support both JSON and FormData
    if request.content_type and "multipart/form-data" in request.content_type:
        title = request.form.get("title", "").strip()
        customer_name = request.form.get("customer_name", "").strip()
        scenario = request.form.get("scenario", "").strip()
        template = request.form.get("template", "").strip()
        requirements = json.loads(request.form.get("requirements", "[]"))
        technologies = json.loads(request.form.get("technologies", "[]"))
        files = request.files.getlist("files")
    else:
        data = request.get_json(force=True) or {}
        title = data.get("title", "").strip()
        customer_name = data.get("customer_name", "").strip()
        scenario = data.get("scenario", "").strip()
        template = data.get("template", "").strip()
        requirements = data.get("requirements", [])
        technologies = data.get("technologies", [])
        files = []

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not customer_name:
        return jsonify({"error": "Customer name is required"}), 400

    # Build issue body with embedded metadata
    metadata = {
        "customer_name": customer_name,
        "scenario": scenario,
        "template": template,
        "requirements": requirements,
        "technologies": technologies,
        "assigned_agents": [],
    }

    body = f"## Demo Request: {title}\n\n"
    body += f"**Customer:** {customer_name}\n"
    if template:
        body += f"**Template:** {template}\n"
    body += f"\n### Scenario\n{scenario}\n\n"
    if requirements:
        body += "### Requirements\n" + "\n".join(f"- {r}" for r in requirements) + "\n\n"
    if technologies:
        body += "### Technologies\n" + "\n".join(f"- {t}" for t in technologies) + "\n\n"
    if files:
        body += "### Attached Files\n" + "\n".join(f"- {f.filename}" for f in files) + "\n\n"
    body += "---\n\n<!-- Metadata (do not edit manually) -->\n```json\n"
    body += json.dumps(metadata, indent=2)
    body += "\n```\n"

    try:
        resp = requests.post(
            f"https://api.github.com/repos/{_GH_REPO}/issues",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"title": f"[Demo] {title}", "body": body, "labels": ["demo"]},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            issue = resp.json()
            _cache["timestamp"] = 0
            return jsonify({
                "id": str(issue["number"]),
                "url": issue["html_url"],
            }), 201
        else:
            return jsonify({"error": f"GitHub API error: {resp.status_code}", "detail": resp.text[:300]}), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
