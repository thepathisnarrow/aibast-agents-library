"""
Fabric Mirroring Agent — configures zero-ETL continuous replication (Mirroring)
from external databases into Microsoft Fabric OneLake.

Supported sources:
  - Azure SQL Database
  - Azure Cosmos DB (NoSQL)
  - Snowflake
  - Azure SQL Managed Instance
  - Azure Database for PostgreSQL
  - Azure Database for MySQL
  - Spark (Databricks / Synapse)

Mirroring vs. Pipelines:
  - Mirroring = zero-ETL, near real-time CDC, managed by Fabric
  - Pipelines = batch or micro-batch ETL with explicit scheduling

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES, get_fabric_auth_preamble


# ── Supported mirroring sources ────────────────────────────────────────────

MIRRORING_SOURCES = {
    "azure_sql": {
        "display": "Azure SQL Database",
        "kind": "AzureSqlDatabase",
        "auth_modes": ["managed_identity", "sql_auth"],
        "docs": "https://learn.microsoft.com/fabric/database/mirrored-database/azure-sql-database",
    },
    "cosmos_db": {
        "display": "Azure Cosmos DB (NoSQL)",
        "kind": "CosmosDb",
        "auth_modes": ["managed_identity", "connection_string"],
        "docs": "https://learn.microsoft.com/fabric/database/mirrored-database/azure-cosmos-db",
    },
    "snowflake": {
        "display": "Snowflake",
        "kind": "Snowflake",
        "auth_modes": ["basic_auth", "key_pair"],
        "docs": "https://learn.microsoft.com/fabric/database/mirrored-database/snowflake",
    },
    "postgres": {
        "display": "Azure Database for PostgreSQL",
        "kind": "PostgreSql",
        "auth_modes": ["managed_identity", "password"],
        "docs": "https://learn.microsoft.com/fabric/database/mirrored-database/azure-database-postgresql",
    },
    "mysql": {
        "display": "Azure Database for MySQL",
        "kind": "MySql",
        "auth_modes": ["password"],
        "docs": "https://learn.microsoft.com/fabric/database/mirrored-database/azure-database-mysql",
    },
    "sql_mi": {
        "display": "Azure SQL Managed Instance",
        "kind": "AzureSqlManagedInstance",
        "auth_modes": ["managed_identity", "sql_auth"],
        "docs": "https://learn.microsoft.com/fabric/database/mirrored-database/azure-sql-managed-instance",
    },
}

# ── Replication states ─────────────────────────────────────────────────────

REPLICATION_STATES = {
    "Running": "✅ Actively replicating changes",
    "Snapshotting": "📷 Initial snapshot in progress",
    "Suspended": "⏸️ Replication paused (check errors)",
    "Failed": "❌ Replication failed — investigate",
    "NotStarted": "🔲 Configured but not started",
}

# ── Microsoft Best Practices (from Microsoft Learn docs) ───────────────────

BEST_PRACTICES = {
    "security": [
        "Prefer Managed Identity authentication over SQL auth/passwords for all Azure sources",
        "Grant minimum required permissions (e.g., db_owner for Azure SQL, Cosmos DB Built-in Data Reader)",
        "Use Fabric system-assigned managed identity for source connectivity",
        "For Snowflake, prefer Entra SSO over username/password when available",
        "Do NOT store connection strings or credentials in plain text — use Azure Key Vault",
    ],
    "performance": [
        "For large bulk data changes, stop and restart mirroring (more efficient than incremental CDC)",
        "If no changes are detected, replicator enters backoff mode (up to 1 hour polling interval)",
        "Inserting/updating billions of records via CDC can be very slow — plan initial loads carefully",
        "Schema changes may require a data change (insert/update/delete) before propagating",
        "For Snowflake, keep PREVENT_UNLOAD_TO_INLINE_URL disabled for optimal staging performance",
    ],
    "limitations": [
        "Max 500–1000 tables per mirrored database (varies by source type)",
        "All tables MUST have a primary key (or clustered index for SQL Server)",
        "Cannot mirror: computed columns, geometry, geography, hierarchyId, sql_variant, timestamp",
        "LOB columns > 1 MB are truncated to 1 MB",
        "Cannot mirror tables using: temporal history, Always Encrypted, in-memory, graph, external",
        "Delayed transaction durability must be disabled on source database",
        "Source database cannot already have CDC, transactional replication, or be mirrored elsewhere",
        "For SQL MI, Update Policy must be 'Always up to date' or 'SQL Server 2025'",
        "Delta lake supports only 6 digits of datetime precision (7th digit is trimmed)",
    ],
    "operational": [
        "Monitor replication states regularly — Failed state requires manual investigation",
        "Set up alerts for replication lag using Fabric monitoring APIs",
        "Test mirroring on non-production databases first before mirroring production workloads",
        "Document which tables are mirrored and maintain a data lineage map",
        "Plan for capacity — mirroring requires F64 or higher (or Trial capacity)",
        "Validate source data types against supported types BEFORE enabling mirroring",
    ],
    "naming_conventions": [
        "Use CAF-compliant naming: mirror-<source>-<database> (e.g., mirror-sqldb-contoso-sales)",
        "Keep mirrored database names descriptive and consistent with source naming",
        "Use workspace naming that reflects environment (dev/test/prod)",
    ],
}


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/fabric-mirroring",
    "version": "1.0.0",
    "display_name": "Fabric Mirroring Agent",
    "description": (
        "Configure zero-ETL mirroring from Azure SQL, Cosmos DB, Snowflake, "
        "PostgreSQL, MySQL into Microsoft Fabric OneLake. Monitors replication "
        "state, validates prerequisites, and generates setup scripts."
    ),
    "author": "Kody",
    "tags": ["fabric", "mirroring", "replication", "zero-etl", "cdc"],
    "category": "data-engineering",
    "quality_tier": "community",
    "dependencies": ["@rapp/basic_agent"],
}


class FabricMirroringAgent(BasicAgent):
    """Creates and manages Fabric Mirrored Databases (zero-ETL replication)."""

    def __init__(self):
        self.name = "fabric_mirroring"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "status", "list_sources", "prerequisites", "monitor", "stop", "resume", "best_practices"],
                        "description": "Action to perform",
                    },
                    "source_type": {
                        "type": "string",
                        "enum": list(MIRRORING_SOURCES.keys()),
                        "description": "Type of source database to mirror",
                    },
                    "workspace": {
                        "type": "string",
                        "description": "Fabric workspace name or ID",
                    },
                    "source_server": {
                        "type": "string",
                        "description": "Source server hostname (e.g. myserver.database.windows.net)",
                    },
                    "source_database": {
                        "type": "string",
                        "description": "Source database name",
                    },
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tables to mirror (empty = all tables)",
                    },
                    "mirrored_db_name": {
                        "type": "string",
                        "description": "Name for the mirrored database item in Fabric",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "list_sources")
        source_type = kwargs.get("source_type", "azure_sql")
        workspace = kwargs.get("workspace", "demo-workspace")
        source_server = kwargs.get("source_server", "<source-server>")
        source_database = kwargs.get("source_database", "<source-db>")
        tables = kwargs.get("tables", [])
        mirrored_db_name = kwargs.get("mirrored_db_name", f"mirror-{source_database}")

        if action == "list_sources":
            return self._list_sources()
        elif action == "prerequisites":
            return self._prerequisites(source_type)
        elif action == "create":
            return self._create_mirror(
                source_type, workspace, source_server, source_database, tables, mirrored_db_name
            )
        elif action == "status":
            return self._status_script(workspace, mirrored_db_name)
        elif action == "monitor":
            return self._monitor_script(workspace, mirrored_db_name)
        elif action == "stop":
            return self._control_script(workspace, mirrored_db_name, "stop")
        elif action == "resume":
            return self._control_script(workspace, mirrored_db_name, "start")
        elif action == "best_practices":
            return self._best_practices()
        else:
            return f"Unknown action: {action}. Use: create, status, list_sources, prerequisites, monitor, stop, resume, best_practices"

    # ── Action handlers ────────────────────────────────────────────────────

    def _list_sources(self):
        lines = ["# Supported Mirroring Sources\n"]
        for key, src in MIRRORING_SOURCES.items():
            auth = ", ".join(src["auth_modes"])
            lines.append(f"**{src['display']}** (`{key}`)")
            lines.append(f"  - Auth: {auth}")
            lines.append(f"  - Docs: {src['docs']}\n")
        lines.append("\n## How Mirroring Works")
        lines.append("1. Fabric takes an initial snapshot of selected tables")
        lines.append("2. CDC (Change Data Capture) streams incremental changes")
        lines.append("3. Data lands in OneLake as Delta Parquet (queryable immediately)")
        lines.append("4. No pipelines, no scheduling — fully managed by Fabric")
        return "\n".join(lines)

    def _prerequisites(self, source_type):
        src = MIRRORING_SOURCES.get(source_type)
        if not src:
            return f"Unknown source: {source_type}. Use: {', '.join(MIRRORING_SOURCES.keys())}"

        common = [
            "## Prerequisites for Mirroring\n",
            f"**Source:** {src['display']}\n",
            "### Fabric Side",
            "- [ ] Fabric capacity (F64 or higher, or Trial capacity)",
            "- [ ] Workspace with Contributor or higher role",
            "- [ ] Mirroring enabled in Fabric admin portal\n",
            "### Source Side",
        ]

        if source_type == "azure_sql":
            common.extend([
                "- [ ] Azure SQL Database (not Free tier)",
                "- [ ] System-assigned managed identity enabled on Fabric",
                "- [ ] Fabric MI granted `db_owner` on the source database",
                "- [ ] CDC enabled: `EXEC sys.sp_cdc_enable_db`",
                "- [ ] Tables must have a primary key",
                "- [ ] TDE with service-managed keys (not CMK)",
                "\n### Enable CDC on source:",
                "```sql",
                "-- Enable CDC on the database",
                "EXEC sys.sp_cdc_enable_db;",
                "",
                "-- Verify",
                "SELECT name, is_cdc_enabled FROM sys.databases WHERE name = DB_NAME();",
                "```",
            ])
        elif source_type == "cosmos_db":
            common.extend([
                "- [ ] Cosmos DB NoSQL API (not Mongo, Cassandra, etc.)",
                "- [ ] Continuous backup enabled (or configure change feed)",
                "- [ ] Fabric MI granted `Cosmos DB Built-in Data Reader` role",
                "- [ ] Containers must have a partition key",
            ])
        elif source_type == "snowflake":
            common.extend([
                "- [ ] Snowflake Enterprise edition or higher",
                "- [ ] Change tracking enabled on tables",
                "- [ ] Service account with SELECT + CHANGE_TRACKING privileges",
                "- [ ] Network access from Fabric to Snowflake (public or private link)",
                "\n### Enable change tracking:",
                "```sql",
                "ALTER TABLE <schema>.<table> SET CHANGE_TRACKING = TRUE;",
                "```",
            ])
        elif source_type == "postgres":
            common.extend([
                "- [ ] Azure Database for PostgreSQL Flexible Server",
                "- [ ] `wal_level = logical` (requires server restart)",
                "- [ ] Fabric MI granted `azure_pg_admin` role",
                "- [ ] Tables must have a primary key",
                "\n### Enable logical replication:",
                "```sql",
                "ALTER SYSTEM SET wal_level = 'logical';",
                "-- Restart required",
                "```",
            ])
        elif source_type == "mysql":
            common.extend([
                "- [ ] Azure Database for MySQL Flexible Server",
                "- [ ] `binlog_format = ROW` and `binlog_row_image = FULL`",
                "- [ ] Fabric connection with read access",
                "- [ ] Tables must have a primary key",
            ])

        common.append(f"\n📖 Full docs: {src['docs']}")
        return "\n".join(common)

    def _create_mirror(self, source_type, workspace, source_server, source_database, tables, mirrored_db_name):
        src = MIRRORING_SOURCES.get(source_type)
        if not src:
            return f"Unknown source: {source_type}"

        auth_preamble = get_fabric_auth_preamble(workspace)
        table_filter = ""
        if tables:
            table_list = json.dumps([{"schemaName": "dbo", "tableName": t} for t in tables], indent=6)
            table_filter = f',\n        "mirroringTableSelection": {table_list}'

        script = (
            f'"""\n'
            f'Create Mirrored Database: {mirrored_db_name}\n'
            f'Source: {src["display"]} → {source_server}/{source_database}\n'
            f'Workspace: {workspace}\n'
            f'"""\n\n'
            f'{auth_preamble}\n'
            f'# Step 1: Create the Mirrored Database item\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'payload = {{\n'
            f'    "displayName": "{mirrored_db_name}",\n'
            f'    "type": "MirroredDatabase",\n'
            f'    "definition": {{\n'
            f'        "parts": [{{\n'
            f'            "path": "mirroring.json",\n'
            f'            "payload": {{\n'
            f'                "source": {{\n'
            f'                    "type": "{src["kind"]}",\n'
            f'                    "typeProperties": {{\n'
            f'                        "server": "{source_server}",\n'
            f'                        "database": "{source_database}"\n'
            f'                    }}\n'
            f'                }}{table_filter}\n'
            f'            }}\n'
            f'        }}]\n'
            f'    }}\n'
            f'}}\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/mirroredDatabases",\n'
            f'    headers=headers,\n'
            f'    json=payload\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'mirror = resp.json()\n'
            f'mirror_id = mirror["id"]\n'
            f'print(f"Created mirrored database: {{mirror_id}}")\n\n'
            f'# Step 2: Start mirroring\n'
            f'start_resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/mirroredDatabases/{{mirror_id}}/startMirroring",\n'
            f'    headers=headers\n'
            f')\n'
            f'start_resp.raise_for_status()\n'
            f'print("Mirroring started — initial snapshot in progress.")\n'
            f'print(f"Monitor at: https://app.fabric.microsoft.com/groups/{{workspace_id}}/mirroreddatabases/{{mirror_id}}")\n'
        )

        return (
            f"## Create Mirrored Database\n\n"
            f"**Source:** {src['display']} (`{source_server}/{source_database}`)\n"
            f"**Target:** Fabric workspace `{workspace}` → `{mirrored_db_name}`\n"
            f"**Tables:** {'All tables' if not tables else ', '.join(tables)}\n\n"
            f"```python\n{script}\n```\n\n"
            f"### What happens next:\n"
            f"1. Initial snapshot copies all selected tables to OneLake (Delta format)\n"
            f"2. CDC replication begins — changes stream in near real-time\n"
            f"3. Query with Spark, SQL endpoint, or Power BI (Direct Lake)\n\n"
            f"### ⚠️ Best Practice Reminders\n"
            f"- **Auth:** Prefer Managed Identity over SQL auth/passwords\n"
            f"- **Primary Keys:** All mirrored tables MUST have a primary key\n"
            f"- **Table Limit:** Max 500–1000 tables depending on source type\n"
            f"- **Data Types:** Unsupported types (geometry, geography, hierarchyId) will be skipped\n"
            f"- **Bulk Changes:** For massive data changes, stop/restart mirroring instead of relying on CDC\n"
            f"- **Monitoring:** Set up monitoring immediately — check status within first hour\n"
        )

    def _status_script(self, workspace, mirrored_db_name):
        auth_preamble = get_fabric_auth_preamble(workspace)
        return (
            f"## Check Mirroring Status\n\n```python\n"
            f'{auth_preamble}\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# List mirrored databases in workspace\n'
            f'resp = requests.get(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/mirroredDatabases",\n'
            f'    headers=headers\n'
            f')\n'
            f'resp.raise_for_status()\n\n'
            f'for db in resp.json().get("value", []):\n'
            f'    if db["displayName"] == "{mirrored_db_name}":\n'
            f'        mirror_id = db["id"]\n'
            f'        # Get mirroring status\n'
            f'        status_resp = requests.get(\n'
            f'            f"{{FABRIC_API}}/workspaces/{{workspace_id}}/mirroredDatabases/{{mirror_id}}/getMirroringStatus",\n'
            f'            headers=headers\n'
            f'        )\n'
            f'        status = status_resp.json()\n'
            f'        print(f"Status: {{status}}")\n'
            f'        break\n'
            f'```\n\n'
            f"### Replication States\n"
            + "\n".join(f"- **{k}**: {v}" for k, v in REPLICATION_STATES.items())
        )

    def _monitor_script(self, workspace, mirrored_db_name):
        auth_preamble = get_fabric_auth_preamble(workspace)
        return (
            f"## Monitor Mirroring (Continuous)\n\n```python\n"
            f'{auth_preamble}\n'
            f'import time\n\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n'
            f'mirror_id = "<mirror-id>"  # From create step\n\n'
            f'while True:\n'
            f'    resp = requests.get(\n'
            f'        f"{{FABRIC_API}}/workspaces/{{workspace_id}}/mirroredDatabases/{{mirror_id}}/getMirroringStatus",\n'
            f'        headers=headers\n'
            f'    )\n'
            f'    status = resp.json()\n'
            f'    tables = status.get("data", [])\n'
            f'    for t in tables:\n'
            f'        print(f"  {{t[\"tableName\"]}}: {{t[\"status\"]}} (rows: {{t.get(\"processedRows\", \"?\")}})")\n'
            f'    print("---")\n'
            f'    time.sleep(30)\n'
            f'```\n'
        )

    def _control_script(self, workspace, mirrored_db_name, action):
        auth_preamble = get_fabric_auth_preamble(workspace)
        endpoint = "stopMirroring" if action == "stop" else "startMirroring"
        verb = "Stopping" if action == "stop" else "Resuming"
        return (
            f"## {verb} Mirroring\n\n```python\n"
            f'{auth_preamble}\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n'
            f'mirror_id = "<mirror-id>"\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/mirroredDatabases/{{mirror_id}}/{endpoint}",\n'
            f'    headers=headers\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'print("{verb} mirroring for {mirrored_db_name}")\n'
            f'```\n'
        )

    def _best_practices(self):
        lines = ["# Microsoft Fabric Mirroring — Best Practices\n"]
        lines.append("*Source: Microsoft Learn documentation (2025)*\n")
        for category, practices in BEST_PRACTICES.items():
            lines.append(f"\n## {category.replace('_', ' ').title()}\n")
            for p in practices:
                lines.append(f"- {p}")
        lines.append("\n\n## Quick Validation Checklist\n")
        lines.append("Before creating a mirrored database, confirm:")
        lines.append("- [ ] Source tables have primary keys")
        lines.append("- [ ] No unsupported column types (geometry, geography, hierarchyId, etc.)")
        lines.append("- [ ] Table count is within limit (≤500 for SQL MI, ≤1000 for SQL Server/Snowflake)")
        lines.append("- [ ] CDC/change tracking enabled on source")
        lines.append("- [ ] Fabric capacity ≥ F64 (or Trial)")
        lines.append("- [ ] Managed Identity configured (preferred over SQL auth)")
        lines.append("- [ ] No conflicting features (CDC, replication, existing mirror)")
        lines.append("- [ ] Delayed transaction durability is DISABLED")
        lines.append(f"\n📖 Docs: https://learn.microsoft.com/fabric/database/mirrored-database/overview")
        return "\n".join(lines)
