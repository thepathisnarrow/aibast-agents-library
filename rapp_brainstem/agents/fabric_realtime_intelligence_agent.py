"""
Fabric Real-Time Intelligence Agent — configures Eventstreams, KQL Databases
(Eventhouse), Real-Time Dashboards, and Activator alerts in Microsoft Fabric.

Covers the full streaming analytics pipeline:
  1. Eventstream (ingest from Event Hubs, IoT Hub, Custom App, Kafka)
  2. KQL Database / Eventhouse (store & query streaming data with KQL)
  3. Real-Time Dashboard (live visualizations over KQL data)
  4. Activator / Data Activator (trigger actions on conditions)

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES, get_fabric_auth_preamble


# ── Eventstream source types ──────────────────────────────────────────────

EVENTSTREAM_SOURCES = {
    "azure_event_hubs": {
        "display": "Azure Event Hubs",
        "kind": "AzureEventHubs",
        "config_keys": ["namespace", "event_hub_name", "consumer_group"],
    },
    "azure_iot_hub": {
        "display": "Azure IoT Hub",
        "kind": "AzureIoTHub",
        "config_keys": ["iot_hub_name", "consumer_group"],
    },
    "custom_app": {
        "display": "Custom App (SDK endpoint)",
        "kind": "CustomApp",
        "config_keys": [],
    },
    "sample_data": {
        "display": "Sample Data (Bicycles/Taxis)",
        "kind": "SampleData",
        "config_keys": ["dataset_name"],
    },
    "kafka": {
        "display": "Apache Kafka",
        "kind": "ApacheKafka",
        "config_keys": ["bootstrap_servers", "topic", "consumer_group"],
    },
    "azure_sql_cdc": {
        "display": "Azure SQL DB (CDC)",
        "kind": "AzureSqlDatabaseCDC",
        "config_keys": ["server", "database", "tables"],
    },
}

# ── Eventstream destinations ──────────────────────────────────────────────

EVENTSTREAM_DESTINATIONS = {
    "kql_database": "KQL Database (Eventhouse)",
    "lakehouse": "Lakehouse (Delta table)",
    "reflex": "Activator (trigger alerts)",
    "derived_stream": "Derived Stream (transformed output)",
    "custom_app": "Custom App (consumer endpoint)",
}

# ── KQL query templates ───────────────────────────────────────────────────

KQL_TEMPLATES = {
    "last_5_min": "{table} | where ingestion_time() > ago(5m) | take 100",
    "count_by_minute": "{table} | summarize count() by bin(Timestamp, 1m) | render timechart",
    "anomaly_detection": (
        "{table} | make-series value=avg({metric}) on Timestamp step 1m "
        "| extend anomalies=series_decompose_anomalies(value)"
    ),
    "top_n": "{table} | summarize count() by {dimension} | top 10 by count_",
    "percentiles": "{table} | summarize percentiles({metric}, 50, 90, 95, 99) by bin(Timestamp, 5m)",
}

# ── Microsoft Best Practices (from Microsoft Learn docs) ───────────────────

BEST_PRACTICES = {
    "eventstream_design": [
        "Use Managed Identity (Entra ID) for Event Hubs/IoT Hub connections — avoid SAS keys",
        "Apply schema alignment and timestamp normalization at the Eventstream level",
        "Use partitioning to scale throughput — match Event Hubs partition count",
        "Route to multiple destinations (KQL + Lakehouse) for hot/cold path architecture",
        "Enable data preview and Data Insights monitoring to verify streaming health",
        "Use derived streams for complex transformations before storing",
    ],
    "eventhouse_kql": [
        "Use Eventhouse as the container for related KQL databases (shared capacity/resources)",
        "Enable 'One Logical Copy' for OneLake data availability when needed",
        "Define retention policies per table based on query patterns (hot/warm/cold)",
        "Use materialized views for frequently computed aggregations",
        "Leverage ingestion batching for high-throughput scenarios (batch size/time settings)",
        "Use streaming ingestion for low-latency requirements (<10 sec end-to-end)",
        "Use .create-merge table for schema evolution without breaking existing queries",
    ],
    "kql_optimization": [
        "Filter early (where clause first) to reduce data scanned",
        "Use ingestion_time() for recent data queries instead of stored timestamps when possible",
        "Avoid 'select *' — project only needed columns",
        "Use summarize with bin() for time-series aggregations (align to appropriate time grain)",
        "Use make-series + series_decompose_anomalies for anomaly detection",
        "Prefer extend over calculated columns for derived values",
        "Use materialized_view() function to reference pre-computed results",
    ],
    "activator_design": [
        "Define clear trigger conditions with appropriate thresholds (avoid alert fatigue)",
        "Use Teams notifications for urgent operational alerts",
        "Use Power Automate flows for complex remediation actions",
        "Set evaluation intervals appropriate to the data velocity",
        "Combine with KQL querysets for complex conditions (CPU > 90% AND trend indicates failure)",
        "Test trigger rules on historical data before activating in production",
    ],
    "security": [
        "Use Microsoft Entra ID (Managed Identity) for all source/destination auth",
        "Store connection strings and keys in Azure Key Vault — never hardcode",
        "Apply workspace RBAC — Contributor or higher for Eventstream management",
        "For custom app sources, rotate shared access keys regularly",
        "Enable audit logging for compliance tracking",
    ],
    "operational": [
        "Monitor Eventstream health via Data Insights tab",
        "Set up alerting on ingestion lag and throughput drops",
        "Plan capacity for burst scenarios (event spikes)",
        "Use sample data sources for development/testing before connecting production streams",
        "Document the full pipeline topology (source → transform → destination)",
        "Name items descriptively: es-<domain>-<source>, eh-<domain>, kqldb-<purpose>",
    ],
}


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/fabric-realtime-intelligence",
    "version": "1.0.0",
    "display_name": "Fabric Real-Time Intelligence Agent",
    "description": (
        "Build streaming analytics in Microsoft Fabric: Eventstreams for ingestion, "
        "KQL Databases (Eventhouse) for querying, Real-Time Dashboards for visualization, "
        "and Activator for alert-driven actions."
    ),
    "author": "Kody",
    "tags": ["fabric", "streaming", "eventstream", "kql", "eventhouse", "activator", "real-time"],
    "category": "data-engineering",
    "quality_tier": "community",
    "dependencies": ["@rapp/basic_agent"],
}


class FabricRealTimeIntelligenceAgent(BasicAgent):
    """Builds real-time streaming analytics pipelines in Microsoft Fabric."""

    def __init__(self):
        self.name = "fabric_realtime_intelligence"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "create_eventstream", "create_eventhouse", "create_kql_database",
                            "create_dashboard", "create_activator", "full_pipeline",
                            "kql_query", "list_sources", "best_practices",
                        ],
                        "description": "Action to perform",
                    },
                    "workspace": {
                        "type": "string",
                        "description": "Fabric workspace name",
                    },
                    "name": {
                        "type": "string",
                        "description": "Name for the item being created",
                    },
                    "source_type": {
                        "type": "string",
                        "enum": list(EVENTSTREAM_SOURCES.keys()),
                        "description": "Eventstream source type",
                    },
                    "destination_type": {
                        "type": "string",
                        "enum": list(EVENTSTREAM_DESTINATIONS.keys()),
                        "description": "Eventstream destination type",
                    },
                    "source_config": {
                        "type": "object",
                        "description": "Source-specific configuration (namespace, topic, etc.)",
                    },
                    "kql_query_type": {
                        "type": "string",
                        "enum": list(KQL_TEMPLATES.keys()),
                        "description": "Pre-built KQL query template to use",
                    },
                    "table_name": {
                        "type": "string",
                        "description": "KQL table name for queries",
                    },
                    "alert_condition": {
                        "type": "string",
                        "description": "Condition expression for Activator (e.g. 'temperature > 80')",
                    },
                    "alert_action": {
                        "type": "string",
                        "enum": ["email", "teams", "power_automate", "custom_webhook"],
                        "description": "What to do when alert fires",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "list_sources")
        workspace = kwargs.get("workspace", "demo-workspace")
        name = kwargs.get("name", "")
        source_type = kwargs.get("source_type", "azure_event_hubs")
        destination_type = kwargs.get("destination_type", "kql_database")
        source_config = kwargs.get("source_config", {})
        kql_query_type = kwargs.get("kql_query_type", "last_5_min")
        table_name = kwargs.get("table_name", "Events")
        alert_condition = kwargs.get("alert_condition", "value > threshold")
        alert_action = kwargs.get("alert_action", "teams")

        handlers = {
            "list_sources": lambda: self._list_sources(),
            "create_eventstream": lambda: self._create_eventstream(
                workspace, name or "es-demo", source_type, destination_type, source_config
            ),
            "create_eventhouse": lambda: self._create_eventhouse(workspace, name or "eh-demo"),
            "create_kql_database": lambda: self._create_kql_database(workspace, name or "kqldb-demo"),
            "create_dashboard": lambda: self._create_dashboard(workspace, name or "rtd-demo", table_name),
            "create_activator": lambda: self._create_activator(
                workspace, name or "alert-demo", alert_condition, alert_action, table_name
            ),
            "full_pipeline": lambda: self._full_pipeline(
                workspace, name or "streaming-demo", source_type, source_config, table_name
            ),
            "kql_query": lambda: self._kql_query(kql_query_type, table_name, kwargs),
            "best_practices": lambda: self._best_practices(),
        }

        handler = handlers.get(action)
        if handler:
            return handler()
        return f"Unknown action: {action}"

    # ── Handlers ───────────────────────────────────────────────────────────

    def _list_sources(self):
        lines = ["# Eventstream Sources\n"]
        for key, src in EVENTSTREAM_SOURCES.items():
            config = ", ".join(src["config_keys"]) if src["config_keys"] else "none"
            lines.append(f"**{src['display']}** (`{key}`)")
            lines.append(f"  - Config: {config}\n")
        lines.append("\n# Destinations\n")
        for key, desc in EVENTSTREAM_DESTINATIONS.items():
            lines.append(f"- `{key}`: {desc}")
        return "\n".join(lines)

    def _create_eventstream(self, workspace, name, source_type, dest_type, source_config):
        auth = get_fabric_auth_preamble(workspace)
        src = EVENTSTREAM_SOURCES.get(source_type, EVENTSTREAM_SOURCES["azure_event_hubs"])

        script = (
            f'"""\n'
            f'Create Eventstream: {name}\n'
            f'Source: {src["display"]} → Destination: {EVENTSTREAM_DESTINATIONS.get(dest_type, dest_type)}\n'
            f'"""\n\n'
            f'{auth}\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# Step 1: Create the Eventstream item\n'
            f'payload = {{\n'
            f'    "displayName": "{name}",\n'
            f'    "type": "Eventstream"\n'
            f'}}\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/eventstreams",\n'
            f'    headers=headers,\n'
            f'    json=payload\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'es_id = resp.json()["id"]\n'
            f'print(f"Eventstream created: {{es_id}}")\n\n'
            f'# Step 2: Configure source ({src["display"]})\n'
            f'# Navigate to: https://app.fabric.microsoft.com\n'
            f'# Open the Eventstream → Add Source → {src["display"]}\n'
            f'# Configuration keys: {", ".join(src["config_keys"]) or "auto-generated endpoint"}\n\n'
            f'# Step 3: Add destination ({EVENTSTREAM_DESTINATIONS.get(dest_type, dest_type)})\n'
            f'# In Eventstream canvas → Add Destination → {dest_type}\n'
            f'# Connect to your KQL Database or Lakehouse\n\n'
            f'print(f"Configure source and destination in Fabric portal:")\n'
            f'print(f"  https://app.fabric.microsoft.com/groups/{{workspace_id}}/eventstreams/{{es_id}}")\n'
        )

        return (
            f"## Create Eventstream: `{name}`\n\n"
            f"**Source:** {src['display']}\n"
            f"**Destination:** {EVENTSTREAM_DESTINATIONS.get(dest_type, dest_type)}\n\n"
            f"```python\n{script}\n```\n"
        )

    def _create_eventhouse(self, workspace, name):
        auth = get_fabric_auth_preamble(workspace)
        script = (
            f'{auth}\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# Create Eventhouse (contains KQL databases)\n'
            f'payload = {{\n'
            f'    "displayName": "{name}",\n'
            f'    "type": "Eventhouse"\n'
            f'}}\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/eventhouses",\n'
            f'    headers=headers,\n'
            f'    json=payload\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'eh = resp.json()\n'
            f'print(f"Eventhouse created: {{eh[\'id\']}}")\n'
            f'print(f"A default KQL database is auto-created with the eventhouse.")\n'
        )
        return f"## Create Eventhouse: `{name}`\n\n```python\n{script}\n```\n"

    def _create_kql_database(self, workspace, name):
        auth = get_fabric_auth_preamble(workspace)
        script = (
            f'{auth}\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# Create KQL Database inside an Eventhouse\n'
            f'eventhouse_id = "<eventhouse-id>"  # From create_eventhouse step\n\n'
            f'payload = {{\n'
            f'    "displayName": "{name}",\n'
            f'    "type": "KQLDatabase",\n'
            f'    "creationPayload": {{\n'
            f'        "databaseType": "ReadWrite",\n'
            f'        "parentEventhouseItemId": eventhouse_id\n'
            f'    }}\n'
            f'}}\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/kqlDatabases",\n'
            f'    headers=headers,\n'
            f'    json=payload\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'kqldb = resp.json()\n'
            f'print(f"KQL Database created: {{kqldb[\'id\']}}")\n\n'
            f'# Create ingestion table\n'
            f'# Run this KQL command in the database:\n'
            f'kql_create_table = """\n'
            f'.create table Events (\n'
            f'    Timestamp: datetime,\n'
            f'    DeviceId: string,\n'
            f'    Temperature: real,\n'
            f'    Humidity: real,\n'
            f'    Status: string\n'
            f')\n'
            f'"""\n'
            f'print("Run in KQL query editor:")\n'
            f'print(kql_create_table)\n'
        )
        return f"## Create KQL Database: `{name}`\n\n```python\n{script}\n```\n"

    def _create_dashboard(self, workspace, name, table_name):
        auth = get_fabric_auth_preamble(workspace)
        return (
            f"## Create Real-Time Dashboard: `{name}`\n\n"
            f"```python\n{auth}\n"
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'payload = {{\n'
            f'    "displayName": "{name}",\n'
            f'    "type": "RTDashboard"\n'
            f'}}\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/items",\n'
            f'    headers=headers,\n'
            f'    json=payload\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'dashboard = resp.json()\n'
            f'print(f"Real-Time Dashboard created: {{dashboard[\'id\']}}")\n'
            f'```\n\n'
            f"### Suggested Tiles (KQL queries)\n\n"
            f"| Tile | KQL |\n|------|-----|\n"
            f"| Event Count (5m) | `{table_name} \\| where ingestion_time() > ago(5m) \\| count` |\n"
            f"| Timechart | `{table_name} \\| summarize count() by bin(Timestamp, 1m) \\| render timechart` |\n"
            f"| Top Devices | `{table_name} \\| summarize count() by DeviceId \\| top 5 by count_` |\n"
            f"| Anomalies | `{table_name} \\| make-series avg(Temperature) on Timestamp step 1m \\| extend anomalies=series_decompose_anomalies(...)` |\n"
        )

    def _create_activator(self, workspace, name, condition, action, table_name):
        auth = get_fabric_auth_preamble(workspace)
        action_config = {
            "email": "Send an email notification",
            "teams": "Post a message to Microsoft Teams channel",
            "power_automate": "Trigger a Power Automate flow",
            "custom_webhook": "POST to a custom webhook URL",
        }
        return (
            f"## Create Activator (Data Activator): `{name}`\n\n"
            f"**Condition:** `{condition}`\n"
            f"**Action:** {action_config.get(action, action)}\n\n"
            f"```python\n{auth}\n"
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# Create Activator item\n'
            f'payload = {{\n'
            f'    "displayName": "{name}",\n'
            f'    "type": "Reflex"\n'
            f'}}\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/items",\n'
            f'    headers=headers,\n'
            f'    json=payload\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'reflex = resp.json()\n'
            f'print(f"Activator created: {{reflex[\'id\']}}")\n'
            f'print("Configure trigger rule in Fabric portal:")\n'
            f'print(f"  Condition: {condition}")\n'
            f'print(f"  Action: {action_config.get(action, action)}")\n'
            f'```\n\n'
            f"### Configuration Steps\n"
            f"1. Open the Activator in Fabric portal\n"
            f"2. Connect to your Eventstream or KQL database (`{table_name}`)\n"
            f"3. Define trigger: **when** `{condition}` → **do** {action_config.get(action, action)}\n"
            f"4. Activate the rule\n"
        )

    def _full_pipeline(self, workspace, name, source_type, source_config, table_name):
        """Generate the complete streaming pipeline setup."""
        sections = [
            f"# Full Real-Time Intelligence Pipeline: `{name}`\n",
            f"**Workspace:** {workspace}\n",
            f"**Flow:** {EVENTSTREAM_SOURCES.get(source_type, {}).get('display', source_type)} "
            f"→ Eventstream → KQL Database → Real-Time Dashboard + Activator\n\n",
            "---\n",
            self._create_eventhouse(workspace, f"{name}-eventhouse"),
            "\n---\n",
            self._create_kql_database(workspace, f"{name}-kqldb"),
            "\n---\n",
            self._create_eventstream(workspace, f"es-{name}", source_type, "kql_database", source_config),
            "\n---\n",
            self._create_dashboard(workspace, f"rtd-{name}", table_name),
            "\n---\n",
            self._create_activator(workspace, f"alert-{name}", "Temperature > 80", "teams", table_name),
            "\n---\n",
            "## Pipeline Summary\n\n"
            "```\n"
            f"[Source: {EVENTSTREAM_SOURCES.get(source_type, {}).get('display', source_type)}]\n"
            f"       │\n"
            f"       ▼\n"
            f"[Eventstream: es-{name}]  ← transform / filter / enrich\n"
            f"       │\n"
            f"       ├──▶ [KQL Database: {name}-kqldb]  ← query with KQL\n"
            f"       │         │\n"
            f"       │         ├──▶ [Real-Time Dashboard: rtd-{name}]\n"
            f"       │         └──▶ [Activator: alert-{name}]\n"
            f"       │\n"
            f"       └──▶ [Lakehouse: bronze]  ← long-term storage (optional)\n"
            f"```\n"
        ]
        return "\n".join(sections)

    def _kql_query(self, query_type, table_name, kwargs):
        template = KQL_TEMPLATES.get(query_type, KQL_TEMPLATES["last_5_min"])
        metric = kwargs.get("metric", "Temperature")
        dimension = kwargs.get("dimension", "DeviceId")
        query = template.format(table=table_name, metric=metric, dimension=dimension)
        return (
            f"## KQL Query: `{query_type}`\n\n"
            f"```kql\n{query}\n```\n\n"
            f"Run this in your KQL Database query editor or from a Real-Time Dashboard tile."
        )

    def _best_practices(self):
        lines = ["# Fabric Real-Time Intelligence — Best Practices\n"]
        lines.append("*Source: Microsoft Learn documentation (2025)*\n")
        for category, practices in BEST_PRACTICES.items():
            lines.append(f"\n## {category.replace('_', ' ').title()}\n")
            for p in practices:
                lines.append(f"- {p}")
        lines.append("\n\n## Architecture Pattern: Hot/Cold Path\n")
        lines.append("```")
        lines.append("[Source] → [Eventstream]")
        lines.append("                │")
        lines.append("                ├─→ [KQL Database] (HOT: real-time queries, <5min latency)")
        lines.append("                │        │")
        lines.append("                │        ├─→ [Real-Time Dashboard] (live visualization)")
        lines.append("                │        └─→ [Activator] (automated alerts/actions)")
        lines.append("                │")
        lines.append("                └─→ [Lakehouse] (COLD: long-term storage, batch analytics)")
        lines.append("```")
        lines.append(f"\n📖 Docs: https://learn.microsoft.com/fabric/real-time-intelligence/overview")
        return "\n".join(lines)
