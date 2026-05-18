"""
Fabric Admin Agent — provisions Fabric workspaces under the MEA account
and grants the SE account ownership.

Dual-Identity Workflow:
  1. MEA (admin@MngEnvMCAP874580.onmicrosoft.com) creates the workspace via Fabric REST API,
     optionally assigning a capacity at creation time.
  2. SE (davidwinegar@microsoft.com) is added as workspace Admin via Power BI Admin API.

This ensures the workspace is created by a tenant-native account (required for
capacity assignment) and the SE can manage it from their own identity.

Drop this file into any brainstem agents/ directory.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES


# ── Constants ──────────────────────────────────────────────────────────────

FABRIC_API = "https://api.fabric.microsoft.com/v1"
PBI_ADMIN_API = "https://api.powerbi.com/v1.0/myorg/admin"

__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/fabric-admin",
    "version": "1.0.0",
    "display_name": "Fabric Admin",
    "description": (
        "Provision Fabric workspaces under the MEA account with capacity assignment, "
        "then grant the SE account workspace Admin rights."
    ),
    "author": "Kody",
    "tags": ["fabric", "admin", "workspace", "capacity", "provisioning"],
    "category": "infrastructure",
    "quality_tier": "community",
    "dependencies": ["@rapp/basic_agent"],
}


class FabricAdminAgent(BasicAgent):
    """Provisions Fabric workspaces (MEA creates, SE gets ownership)."""

    def __init__(self):
        self.name = "fabric_admin"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "create_workspace",
                            "list_workspaces",
                            "delete_workspace",
                            "assign_capacity",
                            "add_member",
                        ],
                        "description": "Action to perform",
                    },
                    "workspace_name": {
                        "type": "string",
                        "description": "Display name for the workspace",
                    },
                    "workspace_id": {
                        "type": "string",
                        "description": "Workspace GUID (for operations on existing workspaces)",
                    },
                    "capacity_id": {
                        "type": "string",
                        "description": "Fabric capacity GUID to assign (optional, uses default if not specified)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Workspace description",
                    },
                    "member_email": {
                        "type": "string",
                        "description": "Email to add as workspace member (defaults to SE login_hint)",
                    },
                    "member_role": {
                        "type": "string",
                        "enum": ["Admin", "Member", "Contributor", "Viewer"],
                        "description": "Role for the member (defaults to Admin)",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action")
        handlers = {
            "create_workspace": self._create_workspace,
            "list_workspaces": self._list_workspaces,
            "delete_workspace": self._delete_workspace,
            "assign_capacity": self._assign_capacity,
            "add_member": self._add_member,
        }
        handler = handlers.get(action)
        if handler:
            return handler(**kwargs)
        return f"Unknown action: {action}"

    # ── Handlers ───────────────────────────────────────────────────────────

    def _create_workspace(self, **kwargs):
        """Create a workspace under MEA and add SE as Admin."""
        workspace_name = kwargs.get("workspace_name", "New Workspace")
        capacity_id = kwargs.get("capacity_id", "")
        description = kwargs.get("description", "")
        se_email = kwargs.get("member_email", TARGET_M365_TENANT["login_hint"])

        lines = []
        lines.append(f"# Create Fabric Workspace: {workspace_name}\n")
        lines.append("## Execution Plan\n")
        lines.append(f"1. **MEA** (`{TARGET_M365_TENANT['mea_admin']}`) creates workspace via Fabric API")
        if capacity_id:
            lines.append(f"2. Capacity `{capacity_id}` assigned at creation time")
        lines.append(f"3. Workspace managed identity provisioned (for Azure resource access)")
        lines.append(f"4. **SE** (`{se_email}`) added as workspace Admin via Power BI Admin API\n")

        # Step 1: Create workspace
        lines.append("## az CLI Commands\n")
        lines.append("```powershell")
        lines.append("# Step 1: Create workspace as MEA (authenticated via az login at startup)")

        body = {"displayName": workspace_name}
        if capacity_id:
            body["capacityId"] = capacity_id
        if description:
            body["description"] = description

        body_json = json.dumps(body, indent=2)
        lines.append(f"$body = @'\n{body_json}\n'@")
        lines.append(f'[System.IO.File]::WriteAllText("$env:TEMP\\fabric_create_ws.json", $body)')
        lines.append(f'$result = az rest --method post --url "{FABRIC_API}/workspaces" `')
        lines.append(f'  --resource "https://api.fabric.microsoft.com" `')
        lines.append(f'  --headers "Content-Type=application/json" `')
        lines.append(f'  --body "@$env:TEMP\\fabric_create_ws.json" | ConvertFrom-Json')
        lines.append(f'$workspaceId = $result.id')
        lines.append(f'"Workspace created: $workspaceId"')
        lines.append("")

        # Step 2: Provision workspace managed identity
        lines.append(f"# Step 2: Provision workspace managed identity (for Azure resource access)")
        lines.append(f'az rest --method post `')
        lines.append(f'  --url "{FABRIC_API}/workspaces/$workspaceId/assignWorkspaceIdentity" `')
        lines.append(f'  --resource "https://api.fabric.microsoft.com"')
        lines.append(f'"Workspace identity provisioned"')
        lines.append("")

        # Step 3: Add SE as Admin
        lines.append(f"# Step 3: Add SE as workspace Admin")
        add_body = json.dumps({"emailAddress": se_email, "groupUserAccessRight": "Admin"}, indent=2)
        lines.append(f"$addBody = @'\n{add_body}\n'@")
        lines.append(f'[System.IO.File]::WriteAllText("$env:TEMP\\fabric_add_se.json", $addBody)')
        lines.append(f'az rest --method post `')
        lines.append(f'  --url "{PBI_ADMIN_API}/groups/$workspaceId/users" `')
        lines.append(f'  --resource "https://analysis.windows.net/powerbi/api" `')
        lines.append(f'  --headers "Content-Type=application/json" `')
        lines.append(f'  --body "@$env:TEMP\\fabric_add_se.json"')
        lines.append(f'"SE ({se_email}) added as Admin"')
        lines.append("```\n")

        # Verification
        lines.append("## Verification\n")
        lines.append("```powershell")
        lines.append("# Verify workspace exists and is on dedicated capacity")
        lines.append(f"$url = '{PBI_ADMIN_API}/groups?$filter=name eq ''{workspace_name}''&$top=10'")
        lines.append(f'az rest --method get --url $url --resource "https://analysis.windows.net/powerbi/api"')
        lines.append("# Check: isOnDedicatedCapacity should be true, state should be Active")
        lines.append("```")

        return "\n".join(lines)

    def _list_workspaces(self, **kwargs):
        """List all workspaces visible to MEA."""
        lines = []
        lines.append("# List Fabric Workspaces\n")
        lines.append("```powershell")
        lines.append("# List workspaces accessible to MEA")
        lines.append(f'az rest --method get --url "{FABRIC_API}/workspaces" `')
        lines.append(f'  --resource "https://api.fabric.microsoft.com" `')
        lines.append(f'  --query "value[].{{name:displayName, id:id, type:type, capacity:capacityId}}" `')
        lines.append(f'  --output table')
        lines.append("```")
        return "\n".join(lines)

    def _delete_workspace(self, **kwargs):
        """Delete a workspace (requires explicit approval per safety constraints)."""
        workspace_id = kwargs.get("workspace_id", "<workspace-id>")
        workspace_name = kwargs.get("workspace_name", "")

        lines = []
        lines.append(f"# Delete Workspace{f': {workspace_name}' if workspace_name else ''}\n")
        lines.append(f"⚠️  **SAFETY GATE**: This requires explicit approval from {self.safety_constraints['no_delete_without_approval'][:20]}...\n")
        lines.append("```powershell")
        lines.append(f"# Delete workspace (MEA must be workspace Admin)")
        lines.append(f'az rest --method delete `')
        lines.append(f'  --url "{FABRIC_API}/workspaces/{workspace_id}" `')
        lines.append(f'  --resource "https://api.fabric.microsoft.com"')
        lines.append(f'"EXIT: $LASTEXITCODE"  # Expect 0 (204 No Content)')
        lines.append("```")
        return "\n".join(lines)

    def _assign_capacity(self, **kwargs):
        """Assign a capacity to an existing workspace."""
        workspace_id = kwargs.get("workspace_id", "<workspace-id>")
        capacity_id = kwargs.get("capacity_id", "<capacity-id>")

        lines = []
        lines.append(f"# Assign Capacity to Workspace\n")
        lines.append("```powershell")
        body = json.dumps({"capacityId": capacity_id})
        lines.append(f'$body = \'{body}\'')
        lines.append(f'[System.IO.File]::WriteAllText("$env:TEMP\\fabric_assign_cap.json", $body)')
        lines.append(f'az rest --method post `')
        lines.append(f'  --url "{FABRIC_API}/workspaces/{workspace_id}/assignToCapacity" `')
        lines.append(f'  --resource "https://api.fabric.microsoft.com" `')
        lines.append(f'  --headers "Content-Type=application/json" `')
        lines.append(f'  --body "@$env:TEMP\\fabric_assign_cap.json"')
        lines.append(f'"EXIT: $LASTEXITCODE"')
        lines.append("```")
        return "\n".join(lines)

    def _add_member(self, **kwargs):
        """Add a user to a workspace via Power BI Admin API."""
        workspace_id = kwargs.get("workspace_id", "<workspace-id>")
        member_email = kwargs.get("member_email", TARGET_M365_TENANT["login_hint"])
        member_role = kwargs.get("member_role", "Admin")

        lines = []
        lines.append(f"# Add Member to Workspace\n")
        lines.append(f"- **Email**: {member_email}")
        lines.append(f"- **Role**: {member_role}\n")
        lines.append("```powershell")
        body = json.dumps({"emailAddress": member_email, "groupUserAccessRight": member_role})
        lines.append(f'$body = \'{body}\'')
        lines.append(f'[System.IO.File]::WriteAllText("$env:TEMP\\fabric_add_member.json", $body)')
        lines.append(f'az rest --method post `')
        lines.append(f'  --url "{PBI_ADMIN_API}/groups/{workspace_id}/users" `')
        lines.append(f'  --resource "https://analysis.windows.net/powerbi/api" `')
        lines.append(f'  --headers "Content-Type=application/json" `')
        lines.append(f'  --body "@$env:TEMP\\fabric_add_member.json"')
        lines.append(f'"EXIT: $LASTEXITCODE"')
        lines.append("```")
        return "\n".join(lines)
