"""
Fabric Architect Agent — designs Fabric workspace topology for a demo:
which workspace(s), which items (Lakehouse / Warehouse / SQL DB / Eventhouse /
Semantic Model / Data Agent / Dataflow / Pipeline / Notebook), which
connections, which roles.

Always reuses the EXISTING Fabric capacity (never creates a new one).
If an existing workspace id is supplied, reuses it; otherwise designs a new
workspace bound to the existing capacity.

This agent does the *design*. Actual item creation is delegated to the
builder agents (data_engineer, fabric_mirroring, fabric_realtime_intelligence,
semantic_model, fabric_data_agent_builder).
"""

from agents.basic_agent import BasicAgent


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/fabric-architect",
    "version": "1.0.0",
    "display_name": "Fabric Architect Agent",
    "description": (
        "Designs Fabric workspace topology: workspace(s), items, connections, "
        "roles. Always reuses the existing Fabric capacity."
    ),
    "tags": ["architect", "fabric", "workspace", "design"],
    "category": "architecture",
}


class FabricArchitectAgent(BasicAgent):
    """Fabric workspace/item topology architect."""

    def __init__(self):
        self.name = "fabric_architect"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["design"],
                        "description": "Produce the Fabric workspace + item design.",
                    },
                    "demo": {
                        "type": "object",
                        "description": "Demo request payload.",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "design")
        if action != "design":
            return f"Unknown action: {action}"
        return self._design(kwargs.get("demo") or {})

    def _design(self, demo: dict) -> str:
        customer = demo.get("customer_name") or "demo"
        title = demo.get("title") or "Demo"
        reqs = demo.get("requirements") or []
        techs = demo.get("technologies") or []
        existing_ws = demo.get("existing_fabric_workspace_id") or ""
        ind = demo.get("industry_primary") or "generic"

        # Decide items
        items: list[tuple[str, str, str]] = []
        items.append(("Lakehouse", f"lh_{_slug(customer)}_bronze", "Raw landing — Delta tables from ingestion (`bronze` layer)."))
        items.append(("Lakehouse", f"lh_{_slug(customer)}_silver", "Conformed, deduplicated (`silver` layer)."))

        wants_warehouse = "Fabric Warehouse" in techs or "Fabric SQL Database" in techs
        if wants_warehouse:
            items.append(("Warehouse", f"wh_{_slug(customer)}_gold", "Gold layer — T-SQL accessible, semantic-model source."))
        else:
            items.append(("Lakehouse", f"lh_{_slug(customer)}_gold", "Gold layer — analytics-ready Delta tables."))

        wants_mirror = "Fabric Mirroring" in techs or any("mirror" in r.lower() for r in reqs)
        if wants_mirror:
            items.append(("Mirrored Database", f"mir_{_slug(customer)}", "Zero-ETL replica of operational store."))

        wants_realtime = "Real-Time Intelligence" in techs or any("stream" in r.lower() or "real-time" in r.lower() for r in reqs)
        if wants_realtime:
            items.append(("Eventstream", f"es_{_slug(customer)}", "Source: Event Hubs (designed by Azure Architect)."))
            items.append(("Eventhouse + KQL DB", f"eh_{_slug(customer)}", "Hot-path analytics; OneLake shortcut for gold."))

        wants_semantic = "Semantic Model / Power BI" in techs or any("power bi" in r.lower() or "bi" in r.lower() for r in reqs)
        if wants_semantic:
            items.append(("Semantic Model", f"sm_{_slug(customer)}", "Direct Lake over gold layer."))
            items.append(("Power BI Report", f"rpt_{_slug(customer)}_exec", "Executive summary layout."))

        wants_data_agent = "Fabric Data Agent" in techs or any("natural language" in r.lower() for r in reqs)
        if wants_data_agent:
            items.append(("Data Agent", f"da_{_slug(customer)}", "NL → SQL on gold; grounding tables: fact + dims."))

        # Pipelines / notebooks always
        items.append(("Notebook", f"nb_{_slug(customer)}_ingest", "PySpark ingestion: source → bronze → silver."))
        items.append(("Pipeline", f"pl_{_slug(customer)}_orch", "Scheduled orchestration of the notebook."))

        # Connections
        conns = []
        if wants_mirror:
            conns.append("- Mirrored source connection (Azure SQL / Cosmos DB) — credentials via MEA managed identity.")
        if wants_realtime:
            conns.append("- Event Hubs connection — namespace from Azure Architect output.")
        if any(t.lower() == "azure storage" for t in techs):
            conns.append("- ADLS Gen2 connection — points at storage account from Azure Architect output.")
        if not conns:
            conns.append("- No external connections required for the bronze layer (uploaded sample data).")

        lines = [
            f"# Fabric Architecture — {title}",
            "",
            f"**Customer:** {customer}",
            f"**Industry:** {ind}",
            f"**Capacity:** *(reuse existing — do not create new)*",
            "",
        ]
        if existing_ws:
            lines.append(f"## Workspace\nReuse existing workspace `{existing_ws}`. Add demo items under a tagged folder (`tag:demo/{_slug(customer)}`).")
        else:
            lines += [
                "## Workspace",
                f"Create a new workspace bound to the EXISTING Fabric capacity:",
                f"- **Name:** `ws-demo-{_slug(customer)}`",
                f"- **Capacity:** existing capacity (do NOT create)",
                f"- **Description:** Demo workspace for {customer} — auto-provisioned by Brainstem.",
                f"- **Admins:** MEA admin + Dave; **Members:** demo team.",
            ]
        lines.append("")
        lines += ["## Items", "| Type | Name | Purpose |", "|------|------|---------|"]
        for typ, name, purpose in items:
            lines.append(f"| {typ} | `{name}` | {purpose} |")
        lines += ["", "## Connections", *conns, ""]
        lines += [
            "## Roles & Sharing",
            "- Workspace Admin: Dave + MEA admin",
            "- Workspace Member: demo team",
            "- Build / use Item-level permissions for the Data Agent (least-privilege grounding).",
            "",
            "## Hand-off",
            "Builder agents called by orchestrator after this design is approved:",
            "- `data_engineer` → provision workspace + lakehouses + notebook + pipeline",
            "- `fabric_mirroring` → mirrored database (if applicable)",
            "- `fabric_realtime_intelligence` → eventstream + eventhouse (if applicable)",
            "- `semantic_model` → semantic model + report (if applicable)",
            "- `fabric_data_agent_builder` → data agent (if applicable)",
        ]
        return "\n".join(lines)


def _slug(s: str) -> str:
    return "".join(c.lower() for c in (s or "demo") if c.isalnum())[:20] or "demo"
