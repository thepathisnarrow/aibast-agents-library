"""
Azure Architect Agent — designs and (when invoked) provisions Azure
foundations for a demo: resource groups, networking, identity, storage,
operational primitives (Event Hubs, SQL, Cosmos DB, etc.).

HARD CONSTRAINTS (NEVER violate):
  - NEVER create a new Fabric capacity. Reuse the existing capacity.
  - NEVER create a new Microsoft Purview account. Reuse the existing one.
  - NEVER delete any Azure resource without explicit approval from Dave
    (see SAFETY_CONSTRAINTS in basic_agent.py).

If the demo design appears to require a new Fabric capacity or Purview
account, this agent must REFUSE and surface the conflict back to the
Enterprise Architect / orchestrator so it can be escalated via ask_user.
"""

import json
from agents.basic_agent import BasicAgent


FORBIDDEN_RESOURCE_TYPES = {
    "microsoft.fabric/capacities",
    "microsoft.powerbidedicated/capacities",  # legacy PBI capacity
    "microsoft.purview/accounts",
}


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/azure-architect",
    "version": "1.0.0",
    "display_name": "Azure Architect Agent",
    "description": (
        "Designs Azure foundations for a demo (resource groups, networking, "
        "identity, storage, operational data services). Will NEVER create a "
        "new Fabric capacity or Purview account — reuses the existing ones."
    ),
    "tags": ["architect", "azure", "iac", "rg", "networking"],
    "category": "architecture",
}


class AzureArchitectAgent(BasicAgent):
    """Azure foundations architect. Reuses existing Fabric / Purview."""

    def __init__(self):
        self.name = "azure_architect"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["design", "validate_request"],
                        "description": "design = produce the Azure design; validate_request = check a requested resource list against hard constraints.",
                    },
                    "demo": {
                        "type": "object",
                        "description": "The demo request (same shape as enterprise_architect).",
                    },
                    "requested_resources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Azure resource type strings to validate (e.g. 'microsoft.storage/storageaccounts').",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "design")
        if action == "validate_request":
            return self._validate(kwargs.get("requested_resources") or [])
        if action == "design":
            return self._design(kwargs.get("demo") or {})
        return f"Unknown action: {action}"

    def _validate(self, requested: list[str]) -> str:
        violations = [r for r in requested if r.lower() in FORBIDDEN_RESOURCE_TYPES]
        if violations:
            return json.dumps({
                "ok": False,
                "violations": violations,
                "message": (
                    "REFUSED — these resource types must be reused, not created: "
                    + ", ".join(violations)
                    + ". Escalate to the Hub SE via ask_user if the demo genuinely needs new ones."
                ),
            }, indent=2)
        return json.dumps({"ok": True, "violations": []}, indent=2)

    def _design(self, demo: dict) -> str:
        customer = demo.get("customer_name") or "demo"
        region = demo.get("azure_region") or "westus3"
        reqs = demo.get("requirements") or []
        techs = demo.get("technologies") or []
        title_slug = (demo.get("title") or "demo").lower().replace(" ", "-")[:24]
        rg_name = f"rg-demo-{_slug(customer)}-{title_slug}"

        # Decide which Azure resources are in scope based on tech selections.
        plan = []
        plan.append(("Resource Group", rg_name, "Single demo RG — all teardown via `az group delete`."))
        plan.append(("Managed Identity (UAMI)", f"id-{_slug(customer)}", "Cross-resource identity for ingestion + Fabric integration."))

        wants_storage = any(t.lower() in ("azure storage",) for t in techs) or any("blob" in r.lower() for r in reqs)
        wants_event_hubs = any("event hub" in t.lower() for t in techs) or any("stream" in r.lower() or "real-time" in r.lower() for r in reqs)
        wants_sql = "Azure SQL" in techs
        wants_cosmos = "Cosmos DB" in techs

        if wants_storage:
            plan.append(("Storage Account (ADLS Gen2)", f"st{_slug(customer)[:18]}data", "Raw landing / source files; HNS enabled."))
        if wants_event_hubs:
            plan.append(("Event Hubs Namespace", f"evhns-{_slug(customer)}", "1 throughput unit, Standard tier — sufficient for demo."))
            plan.append(("Event Hub", "telemetry", "Partitions: 4, retention: 1 day."))
        if wants_sql:
            plan.append(("Azure SQL (Serverless)", f"sql-{_slug(customer)}", "Min vCore for demo; AAD admin = MEA."))
        if wants_cosmos:
            plan.append(("Cosmos DB (Serverless)", f"cosmos-{_slug(customer)}", "SQL API, single region — used as mirroring source."))

        # Conflict check
        violations = []
        # (Heuristic) if the request explicitly contains "Fabric Capacity" or "Purview Account" as a technology
        if any("fabric capacity" in t.lower() for t in techs):
            violations.append("Fabric Capacity")
        if any("purview account" in t.lower() for t in techs):
            violations.append("Purview Account")

        lines = [
            f"# Azure Architecture — {customer}",
            "",
            f"**Region:** `{region}`",
            f"**Resource Group:** `{rg_name}`",
            "",
            "## Resources to Provision",
            "| Type | Name | Notes |",
            "|------|------|-------|",
        ]
        for typ, name, note in plan:
            lines.append(f"| {typ} | `{name}` | {note} |")
        lines += [
            "",
            "## Identity & RBAC",
            "- Use MEA credential (Azure CLI cached) for all create operations.",
            "- Assign UAMI `Storage Blob Data Contributor` on the storage account.",
            "- Assign Fabric capacity admin nothing extra — capacity already exists.",
            "",
            "## Hard Constraints (enforced)",
            "- ❌ No new Fabric capacity will be created — reuse the existing one.",
            "- ❌ No new Purview account will be created — reuse the existing one.",
            "- ❌ No `delete` / `purge` operations without explicit approval from Dave.",
            "",
        ]

        if violations:
            lines += [
                "## ⚠ CONSTRAINT VIOLATION DETECTED",
                "The demo request implies creating: " + ", ".join(violations),
                "This agent will NOT do that. Escalate to the Hub SE via `ask_user` "
                "to confirm whether the existing Fabric capacity / Purview account is acceptable.",
                "",
            ]

        lines += [
            "## Generated Provisioning Commands",
            "```bash",
            f"az group create --name {rg_name} --location {region}",
        ]
        for typ, name, _ in plan[1:]:
            if "Managed Identity" in typ:
                lines.append(f"az identity create --resource-group {rg_name} --name {name}")
            elif "Storage Account" in typ:
                lines.append(f"az storage account create --resource-group {rg_name} --name {name} --location {region} --sku Standard_LRS --kind StorageV2 --hierarchical-namespace true")
            elif "Event Hubs Namespace" in typ:
                lines.append(f"az eventhubs namespace create --resource-group {rg_name} --name {name} --location {region} --sku Standard")
            elif typ == "Event Hub":
                lines.append(f"az eventhubs eventhub create --resource-group {rg_name} --namespace-name evhns-{_slug(customer)} --name {name} --partition-count 4 --message-retention 1")
            elif "Azure SQL" in typ:
                lines.append(f"az sql server create --resource-group {rg_name} --name {name} --location {region} --enable-ad-only-auth")
            elif "Cosmos DB" in typ:
                lines.append(f"az cosmosdb create --resource-group {rg_name} --name {name} --locations regionName={region} --capabilities EnableServerless")
        lines.append("```")
        return "\n".join(lines)


def _slug(s: str) -> str:
    return "".join(c.lower() for c in (s or "demo") if c.isalnum())[:20] or "demo"
