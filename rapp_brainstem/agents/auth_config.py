"""
Shared authentication configuration for RAPP Brainstem data agents.

Dual-Identity Model:
  - SE account (login_hint): The SE's Microsoft identity (e.g. davidwinegar@microsoft.com)
    Used for GitHub/Copilot auth and local identity.
  - MEA account (mea_admin): The tenant-native admin (e.g. admin@MngEnvMCAP874580.onmicrosoft.com)
    Used for ALL Azure/M365/Fabric/Purview operations via `az login`.
    This is the account that has full capacity admin / tenant-native permissions.

At startup, `start.ps1`/`start.sh` authenticates as the MEA via `az login`.
All AzureCliCredential calls then execute under the MEA's identity.

MCAPS Tenant: Each SE's demo environment is hosted in their own MCAPS tenant.
Configuration is loaded from env.yaml (per-user, git-ignored).
Falls back to environment variables, then built-in defaults.

Setup:
  cp env.yaml.example env.yaml   # then fill in your MCAPS values

Usage in generated scripts:
  from agents.auth_config import TARGET_M365_TENANT, get_credential_code, get_az_login_command
"""

import os
import yaml

# ── Load SE-specific configuration from env.yaml ──────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "env.yaml")

def _load_env_config():
    """Load env.yaml if it exists, otherwise return empty dict."""
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

_cfg = _load_env_config()
_tenant_cfg = _cfg.get("tenant", {})
_sub_cfg = _cfg.get("subscription", {})

# ── Target M365 Tenant Configuration ───────────────────────────────────────
# Each SE fills env.yaml with their MngEnvMCAPXXXXXX managed-environment values.
# Env vars override yaml; yaml overrides defaults.

_tenant_domain = (
    os.getenv("MCAPS_TENANT_DOMAIN")
    or _tenant_cfg.get("domain")
    or "MngEnvMCAPXXXXXX.onmicrosoft.com"
)
_login_hint = (
    os.getenv("MCAPS_LOGIN_HINT")
    or _tenant_cfg.get("login_hint")
    or "yourname@microsoft.com"
)
_display_name = (
    os.getenv("MCAPS_DISPLAY_NAME")
    or _tenant_cfg.get("display_name")
    or "MCAPS (Demo Environment)"
)
_mea_admin = (
    os.getenv("MCAPS_MEA_ADMIN")
    or _tenant_cfg.get("mea_admin")
    or f"admin@{_tenant_domain}"
)
_subscription_id = (
    os.getenv("MCAPS_SUBSCRIPTION_ID")
    or _sub_cfg.get("id")
    or "00000000-0000-0000-0000-000000000000"
)
_default_region = (
    os.getenv("MCAPS_DEFAULT_REGION")
    or _sub_cfg.get("default_region")
    or "westus3"
)

TARGET_M365_TENANT = {
    "tenant_id": _tenant_domain,
    "login_hint": _login_hint,
    "display_name": _display_name,
    "authority": f"https://login.microsoftonline.com/{_tenant_domain}",
    "subscription_id": _subscription_id,
    "default_region": _default_region,
    "mea_admin": _mea_admin,
}

# Owner name for safety constraints
OWNER_NAME = os.getenv("OWNER_NAME") or _cfg.get("owner_name") or "Dave"

# Backward-compatible aliases
MCAPS_TENANT = TARGET_M365_TENANT
EXP_TENANT = TARGET_M365_TENANT

# ── Resource scopes for token acquisition ──────────────────────────────────

SCOPES = {
    "fabric": "https://api.fabric.microsoft.com/.default",
    "azure_management": "https://management.azure.com/.default",
    "purview": "https://purview.azure.net/.default",
    "storage": "https://storage.azure.com/.default",
    "eventhubs": "https://eventhubs.azure.net/.default",
    "graph": "https://graph.microsoft.com/.default",
}


def get_credential_code(scope="fabric", include_imports=True):
    """Return Python code snippet that acquires a credential for the MCAPS tenant.

    Uses AzureCliCredential which runs under the MEA identity (set at startup).
    The MEA is the tenant-native admin that has full permissions for
    Azure/Fabric/Purview operations.
    """
    imports = ""
    if include_imports:
        imports = (
            "from azure.identity import AzureCliCredential, DefaultAzureCredential\n"
        )

    resource_scope = SCOPES.get(scope, SCOPES["fabric"])

    return (
        f'{imports}\n'
        f'# Authenticate to target M365 tenant as MEA ({TARGET_M365_TENANT["mea_admin"]})\n'
        f'# (az login was performed at startup as the tenant-native admin)\n'
        f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n\n'
        f'credential = AzureCliCredential(tenant_id=TENANT_ID)\n'
        f'token = credential.get_token("{resource_scope}").token\n'
    )


def get_az_login_command():
    """Return the az CLI login command for the target M365 tenant (as MEA)."""
    return (
        f'# Login to target M365 tenant as MEA (tenant-native admin)\n'
        f'az login --tenant {TARGET_M365_TENANT["tenant_id"]}\n'
        f'az account set --subscription {TARGET_M365_TENANT["subscription_id"]}\n'
        f'# Verify: az account show --query "{{user: user.name, tenant: tenantId, subscription: id}}"\n'
        f'# Expected: {TARGET_M365_TENANT["mea_admin"]} in MCAPS tenant\n'
    )


def get_fabric_auth_preamble(workspace_name=""):
    """Return the standard Fabric REST API auth preamble for target M365 tenant (MEA identity)."""
    return (
        f'# Auth: MEA ({TARGET_M365_TENANT["mea_admin"]}) → target M365 tenant\n'
        f'from azure.identity import AzureCliCredential\n'
        f'import requests\n\n'
        f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n\n'
        f'credential = AzureCliCredential(tenant_id=TENANT_ID)\n'
        f'token = credential.get_token("{SCOPES["fabric"]}").token\n'
        f'headers = {{"Authorization": f"Bearer {{token}}", "Content-Type": "application/json"}}\n\n'
        f'workspace_id = "<your-workspace-id>"  # Workspace: {workspace_name}\n'
    )


def get_purview_auth_preamble(purview_account=""):
    """Return the standard Purview auth preamble for target M365 tenant (MEA identity)."""
    return (
        f'# Auth: MEA ({TARGET_M365_TENANT["mea_admin"]}) → target M365 tenant\n'
        f'from azure.identity import AzureCliCredential\n\n'
        f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n\n'
        f'credential = AzureCliCredential(tenant_id=TENANT_ID)\n'
        f'token = credential.get_token("{SCOPES["purview"]}").token\n'
        f'headers = {{"Authorization": f"Bearer {{token}}", "Content-Type": "application/json"}}\n\n'
        f'PURVIEW = "https://{purview_account}.purview.azure.com"\n'
    )
