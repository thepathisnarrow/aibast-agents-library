"""
Data Engineer Agent — provisions data infrastructure in Microsoft Fabric or Azure,
then guides the user through loading data into those assets.

Two-phase workflow:
  Phase 1: Provision — create Lakehouses, SQL Databases, Storage Accounts, Event Houses, etc.
  Phase 2: Ingest   — ask what data to load and produce the ingestion plan/code.

Follows Microsoft Cloud Adoption Framework (CAF) naming conventions:
  https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming

Key conventions applied:
  - Azure resource abbreviations (st, sql, adf, evh, kv, rg, etc.)
  - Medallion architecture (bronze/silver/gold) for Lakehouse layering
  - Managed identity + DefaultAzureCredential over keys/passwords
  - Resource tagging for cost management and governance
  - Microsoft Entra ID authentication preferred over SQL auth

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
import re
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES, get_fabric_auth_preamble, get_az_login_command


# ── Microsoft CAF Resource Abbreviations ───────────────────────────────────
# https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations

CAF_ABBREVIATIONS = {
    "resource_group": "rg",
    "storage_account": "st",
    "sql_server": "sql",
    "sql_database": "sqldb",
    "synapse_workspace": "syn",
    "eventhub_namespace": "evhns",
    "eventhub": "evh",
    "data_factory": "adf",
    "cosmos_db": "cosmos",
    "adx_cluster": "dec",
    "key_vault": "kv",
    "log_analytics": "log",
    "managed_identity": "id",
    "virtual_network": "vnet",
}

# ── Default Tags (Microsoft governance best practice) ──────────────────────

DEFAULT_TAGS = {
    "provisioned-by": "rapp-brainstem-data-engineer",
    "environment": "dev",
    "cost-center": "",
    "owner": "",
    "project": "",
}


# ── Naming Helper ──────────────────────────────────────────────────────────

def _caf_name(resource_type, workload, environment="dev", instance="001", region="eus2"):
    """Generate a CAF-compliant resource name.
    Pattern: <abbreviation>-<workload>-<environment>-<region>-<instance>
    Storage accounts: <abbreviation><workload><env><instance> (no hyphens, max 24 chars)
    """
    abbrev = CAF_ABBREVIATIONS.get(resource_type, resource_type[:3])
    slug = re.sub(r"[^a-z0-9]", "", workload.lower())[:12]

    # Storage accounts: no hyphens, 3-24 lowercase alphanumeric
    if resource_type == "storage_account":
        name = f"{abbrev}{slug}{environment}{instance}".replace("-", "")[:24]
        return name

    return f"{abbrev}-{slug}-{environment}-{region}-{instance}"


# ── Supported resource types per platform ──────────────────────────────────

FABRIC_RESOURCES = {
    "lakehouse": {
        "display": "Lakehouse",
        "description": "OneLake Delta Lake storage with SQL analytics endpoint and Apache Spark",
        "default_config": {"enable_schemas": True},
        "naming_pattern": "lh_<workload>_<layer>",
        "naming_example": "lh_sales_bronze, lh_sales_silver, lh_sales_gold",
    },
    "sql_database": {
        "display": "Fabric SQL Database",
        "description": "Fabric-native SQL database (T-SQL, fully managed, Microsoft Entra auth)",
        "default_config": {},
        "naming_pattern": "sqldb_<workload>",
        "naming_example": "sqldb_customer_master",
    },
    "eventhouse": {
        "display": "Eventhouse",
        "description": "Real-time analytics engine (KQL) for streaming and event data",
        "default_config": {"cache_period": "31d", "retention_period": "365d"},
        "naming_pattern": "eh_<workload>",
        "naming_example": "eh_telemetry_realtime",
    },
    "warehouse": {
        "display": "Data Warehouse",
        "description": "Enterprise T-SQL data warehouse with cross-database queries",
        "default_config": {},
        "naming_pattern": "dw_<workload>",
        "naming_example": "dw_enterprise_analytics",
    },
    "data_pipeline": {
        "display": "Data Pipeline",
        "description": "Orchestration pipeline for ETL/ELT workflows (Data Factory experience)",
        "default_config": {},
        "naming_pattern": "pl_<source>_to_<destination>",
        "naming_example": "pl_crm_to_lakehouse",
    },
    "notebook": {
        "display": "Notebook",
        "description": "Apache Spark notebook (PySpark, Scala, SparkSQL, R) for data engineering",
        "default_config": {"default_language": "pyspark"},
        "naming_pattern": "nb_<workload>_<purpose>",
        "naming_example": "nb_sales_transform, nb_iot_enrichment",
    },
    "dataflow_gen2": {
        "display": "Dataflow Gen2",
        "description": "Power Query-based data transformation (300+ connectors, no-code/low-code)",
        "default_config": {},
        "naming_pattern": "df_<source>_<destination>",
        "naming_example": "df_sharepoint_to_lakehouse",
    },
    "kql_queryset": {
        "display": "KQL Queryset",
        "description": "Saved KQL queries for Eventhouse real-time analytics",
        "default_config": {},
        "naming_pattern": "kql_<workload>_<purpose>",
        "naming_example": "kql_telemetry_anomalies",
    },
}

AZURE_RESOURCES = {
    "storage_account": {
        "display": "Azure Data Lake Storage Gen2",
        "description": "Hierarchical namespace storage for analytical workloads (Parquet, Delta, CSV)",
        "default_config": {
            "sku": "Standard_LRS",
            "kind": "StorageV2",
            "hns": True,
            "min_tls_version": "TLS1_2",
            "allow_blob_public_access": False,
            "enable_soft_delete": True,
            "soft_delete_days": 7,
        },
        "naming_pattern": "st<workload><env><instance>",
        "naming_example": "stsalesdev001 (3-24 chars, lowercase alphanumeric only)",
    },
    "sql_server": {
        "display": "Azure SQL Database",
        "description": "Managed relational database with Microsoft Entra authentication",
        "default_config": {
            "sku": "GP_S_Gen5_1",
            "max_size_gb": 32,
            "entra_only_auth": True,
            "min_tls_version": "1.2",
            "backup_redundancy": "Local",
        },
        "naming_pattern": "sql-<workload>-<env>-<region>-<instance>",
        "naming_example": "sql-analytics-dev-eus2-001",
    },
    "synapse_workspace": {
        "display": "Azure Synapse Analytics",
        "description": "Unified analytics platform with serverless SQL, Spark, and pipelines",
        "default_config": {
            "managed_vnet": True,
            "public_network_access": "Disabled",
        },
        "naming_pattern": "syn-<workload>-<env>-<region>-<instance>",
        "naming_example": "syn-analytics-dev-eus2-001",
    },
    "eventhub_namespace": {
        "display": "Azure Event Hubs",
        "description": "Cloud-native event streaming platform (millions of events/sec)",
        "default_config": {
            "sku": "Standard",
            "capacity": 1,
            "min_tls_version": "1.2",
            "local_auth_disabled": True,
        },
        "naming_pattern": "evhns-<workload>-<env>-<region>-<instance>",
        "naming_example": "evhns-telemetry-dev-eus2-001",
    },
    "data_factory": {
        "display": "Azure Data Factory",
        "description": "Cloud-scale data integration and ETL/ELT orchestration (90+ connectors)",
        "default_config": {
            "public_network_access": "Disabled",
            "managed_vnet": True,
        },
        "naming_pattern": "adf-<workload>-<env>-<region>-<instance>",
        "naming_example": "adf-ingest-dev-eus2-001",
    },
    "cosmos_db": {
        "display": "Azure Cosmos DB",
        "description": "Globally distributed NoSQL/vector database with multi-model API support",
        "default_config": {
            "api": "NoSQL",
            "offer_throughput": 400,
            "default_consistency": "Session",
            "public_network_access": "Disabled",
            "local_auth_disabled": True,
        },
        "naming_pattern": "cosmos-<workload>-<env>-<region>-<instance>",
        "naming_example": "cosmos-catalog-dev-eus2-001",
    },
    "adx_cluster": {
        "display": "Azure Data Explorer",
        "description": "Fast, fully managed data analytics service for real-time analysis",
        "default_config": {
            "sku": "Dev(No SLA)_Standard_E2a_v4",
            "capacity": 1,
            "enable_streaming_ingest": True,
        },
        "naming_pattern": "dec-<workload>-<env>-<region>-<instance>",
        "naming_example": "dec-iot-dev-eus2-001",
    },
}

# ── Medallion Architecture Layers ─────────────────────────────────────────

MEDALLION_LAYERS = {
    "bronze": {
        "purpose": "Raw ingestion layer — data lands as-is from source systems",
        "format": "Delta (append-only, full fidelity)",
        "naming": "lh_<workload>_bronze",
    },
    "silver": {
        "purpose": "Validated and conformed — deduplicated, typed, joined",
        "format": "Delta (merge/upsert, SCD Type 2 where needed)",
        "naming": "lh_<workload>_silver",
    },
    "gold": {
        "purpose": "Business-ready — aggregated, modeled for consumption (star schema, metrics)",
        "format": "Delta (optimized for BI/reporting, Z-ordered on query columns)",
        "naming": "lh_<workload>_gold",
    },
}


class DataEngineerAgent(BasicAgent):
    """Provisions data infrastructure and guides data loading."""

    def __init__(self):
        self.name = "DataEngineer"
        self.metadata = {
            "name": self.name,
            "description": (
                "Provisions data infrastructure objects (Lakehouses, SQL Databases, "
                "Storage Accounts, Event Houses, Warehouses, Pipelines, etc.) in "
                "Microsoft Fabric or Azure, then asks what data to load and produces "
                "an ingestion plan. Use this agent when the user wants to set up a "
                "data environment or load data into existing assets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list_resources", "provision", "plan_ingestion", "full_setup"],
                        "description": (
                            "Action to perform: "
                            "'list_resources' — show available resource types; "
                            "'provision' — create specified resources; "
                            "'plan_ingestion' — generate a data loading plan for existing assets; "
                            "'full_setup' — provision then prompt for data loading."
                        ),
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["fabric", "azure"],
                        "description": "Target platform. Defaults to 'fabric'.",
                    },
                    "workspace_name": {
                        "type": "string",
                        "description": "Fabric workspace name or Azure resource group.",
                    },
                    "resources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "description": "Resource type key (e.g. 'lakehouse', 'sql_database', 'storage_account')."},
                                "name": {"type": "string", "description": "Display name for the resource."},
                                "config": {"type": "object", "description": "Optional overrides for default configuration."},
                            },
                            "required": ["type", "name"],
                        },
                        "description": "List of resources to provision.",
                    },
                    "data_sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source_type": {
                                    "type": "string",
                                    "enum": ["csv", "parquet", "json", "api", "database", "streaming", "sharepoint", "dataverse", "blob"],
                                    "description": "Type of data source.",
                                },
                                "location": {"type": "string", "description": "Path, URL, or connection string for the source."},
                                "target_resource": {"type": "string", "description": "Name of the provisioned resource to load into."},
                                "description": {"type": "string", "description": "What this data represents."},
                            },
                            "required": ["source_type", "target_resource"],
                        },
                        "description": "Data sources to load (used with 'plan_ingestion' or 'full_setup').",
                    },
                    "use_case": {
                        "type": "string",
                        "description": "High-level description of what the data environment is for. Helps the agent recommend resources and ingestion patterns.",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__(name=self.name, metadata=self.metadata)

    def perform(self, **kwargs):
        action = kwargs.get("action", "list_resources")
        platform = kwargs.get("platform", "fabric")

        if action == "list_resources":
            return self._list_resources(platform)
        elif action == "provision":
            return self._provision(platform, kwargs)
        elif action == "plan_ingestion":
            return self._plan_ingestion(platform, kwargs)
        elif action == "full_setup":
            return self._full_setup(platform, kwargs)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    # ── Actions ────────────────────────────────────────────────────────────

    def _list_resources(self, platform):
        catalog = FABRIC_RESOURCES if platform == "fabric" else AZURE_RESOURCES
        items = []
        for key, info in catalog.items():
            items.append({
                "type": key,
                "display_name": info["display"],
                "description": info["description"],
                "naming_convention": info.get("naming_pattern", ""),
                "naming_example": info.get("naming_example", ""),
            })

        result = {
            "status": "success",
            "platform": platform,
            "available_resources": items,
            "naming_standard": (
                "Microsoft Cloud Adoption Framework (CAF) naming conventions applied. "
                "See: https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming"
            ),
            "hint": (
                "Tell me your use case and I'll recommend which resources to provision. "
                "Or specify resources directly with action='provision'."
            ),
        }

        if platform == "fabric":
            result["medallion_architecture"] = MEDALLION_LAYERS
            result["recommendation"] = (
                "For Lakehouse workloads, use the medallion architecture (bronze/silver/gold) "
                "to separate raw ingestion, validated data, and business-ready consumption layers."
            )

        return json.dumps(result, indent=2)

    def _provision(self, platform, kwargs):
        resources = kwargs.get("resources", [])
        workspace = kwargs.get("workspace_name", "default-workspace")
        use_case = kwargs.get("use_case", "")
        environment = kwargs.get("environment", "dev")
        region = kwargs.get("region", "eastus2")

        if not resources:
            return json.dumps({
                "status": "needs_input",
                "message": (
                    "No resources specified. What would you like to create? "
                    "Provide a use_case and I can recommend, or specify resources directly.\n\n"
                    "Naming convention (CAF): <abbreviation>-<workload>-<environment>-<region>-<instance>\n"
                    "Example: sql-analytics-dev-eus2-001"
                ),
                "available_types": list(
                    FABRIC_RESOURCES.keys() if platform == "fabric" else AZURE_RESOURCES.keys()
                ),
            })

        catalog = FABRIC_RESOURCES if platform == "fabric" else AZURE_RESOURCES
        provisioned = []
        errors = []

        for res in resources:
            res_type = res.get("type", "")
            res_name = res.get("name", "")
            res_config = res.get("config", {})

            if res_type not in catalog:
                errors.append({"type": res_type, "name": res_name, "error": f"Unknown resource type for platform '{platform}'."})
                continue

            # Merge default config with overrides
            final_config = {**catalog[res_type]["default_config"], **res_config}

            # Generate CAF-compliant name suggestion if on Azure
            caf_name_suggestion = None
            if platform == "azure":
                workload_slug = re.sub(r"[^a-z0-9]", "", res_name.lower())[:12]
                caf_name_suggestion = _caf_name(res_type, workload_slug, environment)

            # Apply default tags
            tags = {**DEFAULT_TAGS, "project": use_case[:50] if use_case else ""}
            tags["environment"] = environment

            provisioned.append({
                "type": res_type,
                "display_name": catalog[res_type]["display"],
                "name": res_name,
                "caf_name": caf_name_suggestion,
                "naming_convention": catalog[res_type].get("naming_pattern", ""),
                "platform": platform,
                "workspace": workspace,
                "config": final_config,
                "tags": tags,
                "auth_method": "Microsoft Entra ID (managed identity)" if platform == "azure" else "Microsoft Entra ID (service principal or user)",
                "status": "provisioned",
                "provision_script": self._generate_provision_script(platform, res_type, res_name, workspace, final_config, environment, region),
            })

        result = {
            "status": "success",
            "platform": platform,
            "workspace": workspace,
            "environment": environment,
            "provisioned": provisioned,
            "errors": errors if errors else None,
            "best_practices_applied": [
                "CAF naming conventions",
                "Microsoft Entra ID authentication (no SQL auth / shared keys)",
                "Resource tagging for governance and cost management",
                "TLS 1.2 minimum enforced",
                "Public network access disabled where supported",
                "Managed identity for service-to-service auth",
            ],
            "next_step": (
                "Your data assets are defined. Now -- what data do you want to load into them? "
                "Tell me about your data sources (files, APIs, databases, streams) and "
                "I'll generate the ingestion plan. Use action='plan_ingestion' with data_sources, "
                "or just describe what data you have."
            ),
        }
        if use_case:
            result["use_case"] = use_case

        return json.dumps(result, indent=2)

    def _plan_ingestion(self, platform, kwargs):
        data_sources = kwargs.get("data_sources", [])
        workspace = kwargs.get("workspace_name", "default-workspace")
        use_case = kwargs.get("use_case", "")

        if not data_sources:
            return json.dumps({
                "status": "needs_input",
                "message": (
                    "Assets without data are meaningless. Tell me:\n"
                    "1. What data do you have? (CSVs, APIs, databases, streams, SharePoint lists, Dataverse tables)\n"
                    "2. Where does it live? (local files, URLs, connection strings)\n"
                    "3. Which asset should it land in?\n"
                    "4. How fresh does it need to be? (batch daily, near-real-time, streaming)\n\n"
                    "I'll generate the full ingestion plan with code."
                ),
            })

        ingestion_plans = []
        for source in data_sources:
            source_type = source.get("source_type", "unknown")
            location = source.get("location", "(not specified)")
            target = source.get("target_resource", "(not specified)")
            description = source.get("description", "")

            plan = {
                "source_type": source_type,
                "location": location,
                "target_resource": target,
                "description": description,
                "recommended_method": self._recommend_ingestion_method(platform, source_type, target),
                "code_snippet": self._generate_ingestion_code(platform, source_type, location, target),
            }
            ingestion_plans.append(plan)

        return json.dumps({
            "status": "success",
            "platform": platform,
            "workspace": workspace,
            "use_case": use_case,
            "ingestion_plans": ingestion_plans,
            "summary": f"Generated {len(ingestion_plans)} ingestion plan(s). Review the code snippets and recommended methods above.",
        }, indent=2)

    def _full_setup(self, platform, kwargs):
        """Provision resources, then prompt for data loading."""
        provision_result = json.loads(self._provision(platform, kwargs))

        if provision_result.get("status") == "needs_input":
            return json.dumps(provision_result)

        data_sources = kwargs.get("data_sources")
        if data_sources:
            ingestion_result = json.loads(self._plan_ingestion(platform, kwargs))
            return json.dumps({
                "status": "success",
                "phase_1_provision": provision_result,
                "phase_2_ingestion": ingestion_result,
                "summary": (
                    f"Provisioned {len(provision_result.get('provisioned', []))} resource(s) "
                    f"and planned {len(ingestion_result.get('ingestion_plans', []))} ingestion(s)."
                ),
            }, indent=2)

        # No data sources yet — prompt the user
        provision_result["next_step"] = (
            "Phase 1 complete — your assets are defined. But assets without data are meaningless.\n\n"
            "Now tell me: what data do you want to load?\n"
            "- What format is it in? (CSV, Parquet, JSON, API, database, streaming)\n"
            "- Where does it live? (local path, URL, connection string, SharePoint, Dataverse)\n"
            "- How often does it need to refresh? (one-time, daily, real-time)\n"
            "- What does the data represent? (sales transactions, IoT telemetry, customer records, etc.)\n\n"
            "I'll generate the ingestion pipelines and code to bring it all to life."
        )
        return json.dumps(provision_result, indent=2)

    # ── Script generators ──────────────────────────────────────────────────

    def _generate_provision_script(self, platform, res_type, name, workspace, config, environment="dev", region="eastus2"):
        """Generate platform-specific provisioning code following Microsoft best practices."""
        if platform == "fabric":
            return self._fabric_provision_script(res_type, name, workspace, config)
        else:
            return self._azure_provision_script(res_type, name, workspace, config, environment, region)

    def _fabric_provision_script(self, res_type, name, workspace, config):
        """Generate Fabric REST API provisioning code using EXP tenant auth (davidwin@onemtc.net)."""
        auth_preamble = get_fabric_auth_preamble(workspace)

        # API endpoints per item type
        endpoints = {
            "lakehouse": "lakehouses",
            "sql_database": "sqlDatabases",
            "eventhouse": "eventhouses",
            "warehouse": "warehouses",
            "data_pipeline": "dataPipelines",
            "notebook": "notebooks",
            "dataflow_gen2": "dataflows",
            "kql_queryset": "kqlQuerysets",
        }

        endpoint = endpoints.get(res_type)
        if not endpoint:
            return f"# No script template for '{res_type}' yet."

        return (
            auth_preamble +
            f'url = f"https://api.fabric.microsoft.com/v1/workspaces/{{workspace_id}}/{endpoint}"\n'
            f'body = {{\n'
            f'    "displayName": "{name}",\n'
            f'    "description": "Provisioned by RAPP Brainstem DataEngineer agent"\n'
            f'}}\n\n'
            f'resp = requests.post(url, json=body, headers=headers)\n'
            f'resp.raise_for_status()\n'
            f'print(f"{FABRIC_RESOURCES.get(res_type, {}).get("display", res_type)} created: {{resp.json().get(\'id\', \'unknown\')}}")\n'
        )

    def _azure_provision_script(self, res_type, name, workspace, config, environment="dev", region="eastus2"):
        """Generate Azure CLI provisioning commands following CAF naming and security best practices."""
        rg = workspace
        workload_slug = re.sub(r"[^a-z0-9]", "", name.lower())[:12]
        caf = _caf_name(res_type, workload_slug, environment)
        region_short = region.replace("eastus2", "eus2").replace("eastus", "eus").replace("westus2", "wus2")

        # EXP tenant login preamble
        az_login = (
            f'# ── Authenticate to EXP tenant (demo environment) ──────────────\n'
            f'# az login --tenant {TARGET_M365_TENANT["tenant_id"]} --allow-no-subscriptions\n'
            f'# Logged in as: davidwin@onemtc.net\n'
            f'# ─────────────────────────────────────────────────────────────────\n\n'
        )

        # Common tag string for all resources
        tag_str = (
            f'  --tags '
            f'environment={environment} '
            f'provisioned-by=rapp-brainstem '
            f'project="{name}"'
        )

        scripts = {
            "storage_account": (
                f'# Create Azure Data Lake Storage Gen2 (CAF name: {caf})\n'
                f'# Best practices: HNS enabled, TLS 1.2, no public blob access, soft delete\n'
                f'az storage account create \\\n'
                f'  --name {caf} \\\n'
                f'  --resource-group {rg} \\\n'
                f'  --location {region} \\\n'
                f'  --sku {config.get("sku", "Standard_LRS")} \\\n'
                f'  --kind {config.get("kind", "StorageV2")} \\\n'
                f'  --hns {"true" if config.get("hns", True) else "false"} \\\n'
                f'  --min-tls-version {config.get("min_tls_version", "TLS1_2")} \\\n'
                f'  --allow-blob-public-access {"true" if config.get("allow_blob_public_access", False) else "false"} \\\n'
                f'{tag_str}\n\n'
                f'# Enable soft delete for data protection\n'
                f'az storage blob service-properties delete-policy update \\\n'
                f'  --account-name {caf} \\\n'
                f'  --enable true \\\n'
                f'  --days-retained {config.get("soft_delete_days", 7)}\n\n'
                f'# Create medallion containers\n'
                f'az storage container create --account-name {caf} --name bronze --auth-mode login\n'
                f'az storage container create --account-name {caf} --name silver --auth-mode login\n'
                f'az storage container create --account-name {caf} --name gold --auth-mode login\n'
            ),
            "sql_server": (
                f'# Create Azure SQL Database (CAF name: sql-{workload_slug}-{environment}-{region_short}-001)\n'
                f'# Best practices: Microsoft Entra-only auth, no SQL auth, serverless compute\n'
                f'az sql server create \\\n'
                f'  --name sql-{workload_slug}-{environment}-{region_short}-001 \\\n'
                f'  --resource-group {rg} \\\n'
                f'  --location {region} \\\n'
                f'  --enable-ad-only-auth \\\n'
                f'  --external-admin-principal-type User \\\n'
                f'  --external-admin-name "<your-entra-admin-upn>" \\\n'
                f'  --external-admin-sid "<your-entra-admin-object-id>" \\\n'
                f'  --minimal-tls-version 1.2\n\n'
                f'az sql db create \\\n'
                f'  --name sqldb-{workload_slug} \\\n'
                f'  --server sql-{workload_slug}-{environment}-{region_short}-001 \\\n'
                f'  --resource-group {rg} \\\n'
                f'  --edition GeneralPurpose \\\n'
                f'  --compute-model Serverless \\\n'
                f'  --auto-pause-delay 60 \\\n'
                f'  --min-capacity 0.5 \\\n'
                f'  --backup-storage-redundancy {config.get("backup_redundancy", "Local")} \\\n'
                f'{tag_str}\n'
            ),
            "synapse_workspace": (
                f'# Create Azure Synapse Analytics (CAF name: syn-{workload_slug}-{environment}-{region_short}-001)\n'
                f'# Best practices: managed VNet, disable public access\n'
                f'az synapse workspace create \\\n'
                f'  --name syn-{workload_slug}-{environment}-{region_short}-001 \\\n'
                f'  --resource-group {rg} \\\n'
                f'  --location {region} \\\n'
                f'  --storage-account "<adls-account-name>" \\\n'
                f'  --file-system "synapse" \\\n'
                f'{tag_str}\n\n'
                f'# Enable managed VNet\n'
                f'# Note: Set --managed-virtual-network true at creation for network isolation\n'
            ),
            "eventhub_namespace": (
                f'# Create Azure Event Hubs (CAF name: evhns-{workload_slug}-{environment}-{region_short}-001)\n'
                f'# Best practices: disable local auth, use Microsoft Entra RBAC\n'
                f'az eventhubs namespace create \\\n'
                f'  --name evhns-{workload_slug}-{environment}-{region_short}-001 \\\n'
                f'  --resource-group {rg} \\\n'
                f'  --location {region} \\\n'
                f'  --sku {config.get("sku", "Standard")} \\\n'
                f'  --capacity {config.get("capacity", 1)} \\\n'
                f'  --minimum-tls-version 1.2 \\\n'
                f'  --disable-local-auth {"true" if config.get("local_auth_disabled", True) else "false"} \\\n'
                f'{tag_str}\n\n'
                f'# Assign Azure Event Hubs Data Sender/Receiver role to managed identity\n'
                f'# az role assignment create --assignee "<managed-identity-id>" \\\n'
                f'#   --role "Azure Event Hubs Data Sender" \\\n'
                f'#   --scope "/subscriptions/<sub>/resourceGroups/{rg}/providers/Microsoft.EventHub/namespaces/evhns-{workload_slug}-{environment}-{region_short}-001"\n'
            ),
            "data_factory": (
                f'# Create Azure Data Factory (CAF name: adf-{workload_slug}-{environment}-{region_short}-001)\n'
                f'# Best practices: system-assigned managed identity, Git integration\n'
                f'az datafactory create \\\n'
                f'  --name adf-{workload_slug}-{environment}-{region_short}-001 \\\n'
                f'  --resource-group {rg} \\\n'
                f'  --location {region} \\\n'
                f'{tag_str}\n\n'
                f'# Note: Enable managed VNet via portal or ARM template for network isolation\n'
                f'# Note: Configure Git integration for CI/CD (Azure DevOps or GitHub)\n'
            ),
            "cosmos_db": (
                f'# Create Azure Cosmos DB (CAF name: cosmos-{workload_slug}-{environment}-{region_short}-001)\n'
                f'# Best practices: disable local auth, use RBAC, session consistency\n'
                f'az cosmosdb create \\\n'
                f'  --name cosmos-{workload_slug}-{environment}-{region_short}-001 \\\n'
                f'  --resource-group {rg} \\\n'
                f'  --locations regionName={region} failoverPriority=0 \\\n'
                f'  --default-consistency-level {config.get("default_consistency", "Session")} \\\n'
                f'  --disable-key-based-metadata-write-access true \\\n'
                f'{tag_str}\n\n'
                f'az cosmosdb sql database create \\\n'
                f'  --account-name cosmos-{workload_slug}-{environment}-{region_short}-001 \\\n'
                f'  --resource-group {rg} \\\n'
                f'  --name {workload_slug}-db\n\n'
                f'# Assign Cosmos DB Built-in Data Contributor role to managed identity\n'
                f'# az cosmosdb sql role assignment create \\\n'
                f'#   --account-name cosmos-{workload_slug}-{environment}-{region_short}-001 \\\n'
                f'#   --resource-group {rg} \\\n'
                f'#   --role-definition-id 00000000-0000-0000-0000-000000000002 \\\n'
                f'#   --principal-id "<managed-identity-principal-id>" \\\n'
                f'#   --scope "/"\n'
            ),
            "adx_cluster": (
                f'# Create Azure Data Explorer (CAF name: dec-{workload_slug}-{environment}-{region_short}-001)\n'
                f'# Best practices: streaming ingestion enabled, managed identity\n'
                f'az kusto cluster create \\\n'
                f'  --name dec{workload_slug}{environment}001 \\\n'
                f'  --resource-group {rg} \\\n'
                f'  --location {region} \\\n'
                f'  --sku name="{config.get("sku", "Dev(No SLA)_Standard_E2a_v4")}" capacity={config.get("capacity", 1)} tier="Basic" \\\n'
                f'  --enable-streaming-ingest {"true" if config.get("enable_streaming_ingest", True) else "false"} \\\n'
                f'{tag_str}\n'
            ),
        }
        script = scripts.get(res_type, f"# No script template for '{res_type}' yet.")
        return az_login + script

    def _recommend_ingestion_method(self, platform, source_type, target):
        """Recommend the best ingestion method based on source and target."""
        if platform == "fabric":
            recommendations = {
                "csv": "Use Dataflow Gen2 for small files, or Spark notebook with `spark.read.csv()` for large files. Consider shortcuts for OneLake-referenced data.",
                "parquet": "Create a shortcut to the Parquet location, or use `spark.read.parquet()` in a notebook for transformation.",
                "json": "Spark notebook with `spark.read.json()` or Dataflow Gen2 with JSON connector.",
                "api": "Spark notebook with `requests` library → write to Lakehouse delta tables. Schedule via Data Pipeline.",
                "database": "Dataflow Gen2 with database connector, or Data Pipeline copy activity for bulk loads.",
                "streaming": "Eventhouse with Event Stream connector for real-time ingestion. Use KQL for analytics.",
                "sharepoint": "Dataflow Gen2 with SharePoint Online connector. Maps lists/libraries to tables.",
                "dataverse": "Dataflow Gen2 with Dataverse connector, or create a Lakehouse shortcut to Dataverse managed lake.",
                "blob": "Create a OneLake shortcut to the Azure Blob/ADLS container. Zero-copy, instant access.",
            }
        else:
            recommendations = {
                "csv": "ADF Copy Activity from Blob/ADLS to target. Or `BULK INSERT` for Azure SQL.",
                "parquet": "ADF Copy Activity preserving Parquet format, or OPENROWSET in Synapse serverless.",
                "json": "ADF with JSON dataset, or Event Hubs for streaming JSON payloads.",
                "api": "ADF REST connector with pagination, or Azure Function for complex auth/transform.",
                "database": "ADF Copy Activity with appropriate linked service (SQL, Oracle, MySQL, etc.).",
                "streaming": "Event Hubs → Stream Analytics → target store. Or Event Hubs Capture for batch landing.",
                "sharepoint": "ADF SharePoint Online connector or Power Automate flow to blob.",
                "dataverse": "ADF Dataverse connector, or Synapse Link for Dataverse for continuous sync.",
                "blob": "ADF Copy Activity, or direct mount/access via storage account keys or managed identity.",
            }
        return recommendations.get(source_type, "Custom ingestion logic required. Describe your source and I'll help.")

    def _generate_ingestion_code(self, platform, source_type, location, target):
        """Generate starter ingestion code."""
        if platform == "fabric":
            return self._fabric_ingestion_code(source_type, location, target)
        else:
            return self._azure_ingestion_code(source_type, location, target)

    def _fabric_ingestion_code(self, source_type, location, target):
        """Fabric Spark notebook ingestion code (medallion architecture pattern).
        Note: Runs in EXP tenant Fabric workspace — identity is inherited from
        workspace context (davidwin@onemtc.net). Use mssparkutils.credentials
        for Key Vault access within the same tenant."""
        snippets = {
            "csv": (
                f'# Load CSV into Lakehouse delta table (Bronze layer - raw ingestion)\n'
                f'# Best practice: explicit schema definition for production workloads\n'
                f'df = spark.read.format("csv") \\\n'
                f'    .option("header", "true") \\\n'
                f'    .option("inferSchema", "true") \\\n'
                f'    .option("dateFormat", "yyyy-MM-dd") \\\n'
                f'    .option("timestampFormat", "yyyy-MM-dd\'T\'HH:mm:ss.SSSZ") \\\n'
                f'    .load("{location}")\n\n'
                f'# Add ingestion metadata columns (audit trail)\n'
                f'from pyspark.sql.functions import current_timestamp, lit, input_file_name\n'
                f'df = df.withColumn("_ingested_at", current_timestamp()) \\\n'
                f'       .withColumn("_source_file", input_file_name())\n\n'
                f'df.write.format("delta") \\\n'
                f'    .mode("append") \\\n'
                f'    .option("mergeSchema", "true") \\\n'
                f'    .saveAsTable("{target}")\n\n'
                f'print(f"Loaded {{df.count()}} rows into {target}")\n'
            ),
            "parquet": (
                f'# Load Parquet into Lakehouse (Bronze layer)\n'
                f'# Best practice: Parquet is already columnar — ideal for Delta conversion\n'
                f'from pyspark.sql.functions import current_timestamp, input_file_name\n\n'
                f'df = spark.read.parquet("{location}")\n\n'
                f'df = df.withColumn("_ingested_at", current_timestamp()) \\\n'
                f'       .withColumn("_source_file", input_file_name())\n\n'
                f'df.write.format("delta") \\\n'
                f'    .mode("append") \\\n'
                f'    .option("mergeSchema", "true") \\\n'
                f'    .saveAsTable("{target}")\n\n'
                f'print(f"Loaded {{df.count()}} rows into {target}")\n'
            ),
            "json": (
                f'# Load JSON into Lakehouse (Bronze layer)\n'
                f'from pyspark.sql.functions import current_timestamp, input_file_name\n\n'
                f'df = spark.read.option("multiline", "true").json("{location}")\n\n'
                f'df = df.withColumn("_ingested_at", current_timestamp()) \\\n'
                f'       .withColumn("_source_file", input_file_name())\n\n'
                f'df.write.format("delta") \\\n'
                f'    .mode("append") \\\n'
                f'    .option("mergeSchema", "true") \\\n'
                f'    .saveAsTable("{target}")\n'
            ),
            "api": (
                f'# Ingest from REST API into Lakehouse (Bronze layer)\n'
                f'# Best practice: use managed identity via mssparkutils for auth\n'
                f'import requests\n'
                f'import pandas as pd\n'
                f'from pyspark.sql.functions import current_timestamp, lit\n\n'
                f'# For authenticated APIs, use Key Vault:\n'
                f'# api_key = mssparkutils.credentials.getSecret("<keyvault-name>", "<secret-name>")\n'
                f'response = requests.get("{location}")\n'
                f'response.raise_for_status()\n'
                f'data = response.json()\n\n'
                f'pdf = pd.json_normalize(data)  # flatten nested JSON\n'
                f'df = spark.createDataFrame(pdf)\n'
                f'df = df.withColumn("_ingested_at", current_timestamp()) \\\n'
                f'       .withColumn("_source_api", lit("{location}"))\n\n'
                f'df.write.format("delta") \\\n'
                f'    .mode("append") \\\n'
                f'    .saveAsTable("{target}")\n'
            ),
            "database": (
                f'# Read from external database into Lakehouse\n'
                f'# Best practice: use Key Vault for credentials, avoid inline secrets\n'
                f'# Retrieve credentials securely:\n'
                f'# jdbc_user = mssparkutils.credentials.getSecret("<keyvault-name>", "db-username")\n'
                f'# jdbc_pass = mssparkutils.credentials.getSecret("<keyvault-name>", "db-password")\n\n'
                f'df = spark.read.format("jdbc") \\\n'
                f'    .option("url", "{location}") \\\n'
                f'    .option("dbtable", "<source_table>") \\\n'
                f'    .option("user", jdbc_user) \\\n'
                f'    .option("password", jdbc_pass) \\\n'
                f'    .option("encrypt", "true") \\\n'
                f'    .option("trustServerCertificate", "false") \\\n'
                f'    .load()\n\n'
                f'from pyspark.sql.functions import current_timestamp\n'
                f'df = df.withColumn("_ingested_at", current_timestamp())\n\n'
                f'df.write.format("delta") \\\n'
                f'    .mode("append") \\\n'
                f'    .option("mergeSchema", "true") \\\n'
                f'    .saveAsTable("{target}")\n'
            ),
            "streaming": (
                f'# Stream into Eventhouse via Event Stream\n'
                f'# Configure in Fabric portal:\n'
                f'# 1. Create Event Stream → connect source ({location})\n'
                f'# 2. Add destination: Eventhouse KQL Database → {target}\n'
                f'# 3. Map fields and start streaming\n\n'
                f'# Or use KQL to query ingested data:\n'
                f'# {target}\n'
                f'# | where ingestion_time() > ago(1h)\n'
                f'# | summarize count() by bin(Timestamp, 5m)\n'
            ),
            "blob": (
                f'# Create shortcut to Azure Blob (zero-copy)\n'
                f'# In Fabric portal: Lakehouse → New Shortcut → Azure Data Lake Storage Gen2\n'
                f'# Connection: {location}\n\n'
                f'# Or read directly:\n'
                f'df = spark.read.format("delta").load("{location}")\n'
                f'df.write.format("delta").mode("overwrite").saveAsTable("{target}")\n'
            ),
            "sharepoint": (
                f'# Use Dataflow Gen2 for SharePoint ingestion\n'
                f'# 1. New Dataflow Gen2 in workspace\n'
                f'# 2. Get Data → SharePoint Online list\n'
                f'# 3. URL: {location}\n'
                f'# 4. Transform in Power Query editor\n'
                f'# 5. Set destination: Lakehouse → {target}\n'
            ),
            "dataverse": (
                f'# Option 1: Lakehouse shortcut to Dataverse managed lake\n'
                f'# Lakehouse → New Shortcut → Dataverse\n'
                f'# Select tables from {location}\n\n'
                f'# Option 2: Dataflow Gen2\n'
                f'# New Dataflow Gen2 → Get Data → Dataverse\n'
                f'# Environment: {location}\n'
                f'# Destination: Lakehouse → {target}\n'
            ),
        }
        return snippets.get(source_type, f"# Custom ingestion needed for source_type='{source_type}'")

    def _azure_ingestion_code(self, source_type, location, target):
        """Azure SDK ingestion code authenticating to EXP tenant (davidwin@onemtc.net)."""
        # Auth preamble for all Azure SDK snippets
        auth_block = (
            f'# Authenticate to EXP tenant as davidwin@onemtc.net\n'
            f'from azure.identity import InteractiveBrowserCredential, AzureCliCredential, ChainedTokenCredential\n\n'
            f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n'
            f'credential = ChainedTokenCredential(\n'
            f'    AzureCliCredential(tenant_id=TENANT_ID),\n'
            f'    InteractiveBrowserCredential(tenant_id=TENANT_ID, login_hint="{TARGET_M365_TENANT["login_hint"]}")\n'
            f')\n\n'
        )
        snippets = {
            "csv": (
                auth_block +
                f'from azure.storage.blob import BlobServiceClient\n\n'
                f'blob_service = BlobServiceClient(\n'
                f'    account_url="https://<storage_account>.blob.core.windows.net",\n'
                f'    credential=credential\n'
                f')\n\n'
                f'# Upload to bronze container (raw landing zone)\n'
                f'blob_client = blob_service.get_blob_client("bronze", f"data/{target}.csv")\n'
                f'with open("{location}", "rb") as data:\n'
                f'    blob_client.upload_blob(data, overwrite=True)\n\n'
                f'# For SQL loading, use EXTERNAL DATA SOURCE + OPENROWSET (no keys needed with managed identity)\n'
                f'# BULK INSERT {target} FROM "data/{target}.csv"\n'
                f'# WITH (DATA_SOURCE = "ExternalBronze", FORMAT = "CSV", FIRSTROW = 2)\n'
            ),
            "parquet": (
                f'# Query Parquet directly with Synapse serverless\n'
                f'SELECT * FROM OPENROWSET(\n'
                f'    BULK \'{location}\',\n'
                f'    FORMAT = \'PARQUET\'\n'
                f') AS [data]\n\n'
                f'# Or create external table:\n'
                f'CREATE EXTERNAL TABLE {target} WITH (\n'
                f'    LOCATION = \'{location}\',\n'
                f'    DATA_SOURCE = ExternalDataSource,\n'
                f'    FILE_FORMAT = ParquetFormat\n'
                f')\n'
            ),
            "api": (
                f'# Azure Function to ingest from API (EXP tenant: davidwin@onemtc.net)\n'
                f'import requests\n'
                f'import json\n'
                f'from azure.identity import InteractiveBrowserCredential, AzureCliCredential, ChainedTokenCredential\n'
                f'from azure.storage.blob import BlobServiceClient\n\n'
                f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n'
                f'credential = ChainedTokenCredential(\n'
                f'    AzureCliCredential(tenant_id=TENANT_ID),\n'
                f'    InteractiveBrowserCredential(tenant_id=TENANT_ID, login_hint="{TARGET_M365_TENANT["login_hint"]}")\n'
                f')\n\n'
                f'response = requests.get("{location}")\n'
                f'response.raise_for_status()\n'
                f'data = response.json()\n\n'
                f'blob_service = BlobServiceClient(\n'
                f'    account_url="https://<storage_account>.blob.core.windows.net",\n'
                f'    credential=credential\n'
                f')\n'
                f'container = blob_service.get_container_client("bronze")\n'
                f'container.upload_blob("{target}.json", json.dumps(data), overwrite=True)\n'
            ),
            "streaming": (
                f'# Send events to Event Hubs in EXP tenant (davidwin@onemtc.net)\n'
                f'from azure.identity import InteractiveBrowserCredential, AzureCliCredential, ChainedTokenCredential\n'
                f'from azure.eventhub import EventHubProducerClient, EventData\n\n'
                f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n'
                f'credential = ChainedTokenCredential(\n'
                f'    AzureCliCredential(tenant_id=TENANT_ID),\n'
                f'    InteractiveBrowserCredential(tenant_id=TENANT_ID, login_hint="{TARGET_M365_TENANT["login_hint"]}")\n'
                f')\n\n'
                f'# RBAC: requires "Azure Event Hubs Data Sender" role for davidwin@onemtc.net\n'
                f'producer = EventHubProducerClient(\n'
                f'    fully_qualified_namespace="<namespace>.servicebus.windows.net",\n'
                f'    eventhub_name="{target}",\n'
                f'    credential=credential\n'
                f')\n'
                f'batch = producer.create_batch()\n'
                f'batch.add(EventData(\'{{"source": "{location}"}}\'))\n'
                f'producer.send_batch(batch)\n'
                f'producer.close()\n'
            ),
            "database": (
                f'# ADF pipeline JSON (Copy Activity)\n'
                f'{{\n'
                f'  "name": "Copy_{target}",\n'
                f'  "type": "Copy",\n'
                f'  "source": {{"type": "SqlSource", "sqlReaderQuery": "SELECT * FROM <table>"}},\n'
                f'  "sink": {{"type": "SqlSink", "writeBehavior": "upsert"}},\n'
                f'  "inputs": [{{"referenceName": "SourceDataset"}}],\n'
                f'  "outputs": [{{"referenceName": "{target}_Dataset"}}]\n'
                f'}}\n'
            ),
            "blob": (
                f'# Copy blob using EXP tenant credential (davidwin@onemtc.net)\n'
                f'from azure.identity import InteractiveBrowserCredential, AzureCliCredential, ChainedTokenCredential\n'
                f'from azure.storage.blob import BlobServiceClient\n\n'
                f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n'
                f'credential = ChainedTokenCredential(\n'
                f'    AzureCliCredential(tenant_id=TENANT_ID),\n'
                f'    InteractiveBrowserCredential(tenant_id=TENANT_ID, login_hint="{TARGET_M365_TENANT["login_hint"]}")\n'
                f')\n\n'
                f'source_service = BlobServiceClient(\n'
                f'    account_url="https://<source_account>.blob.core.windows.net",\n'
                f'    credential=credential\n'
                f')\n'
                f'dest_service = BlobServiceClient(\n'
                f'    account_url="https://<dest_account>.blob.core.windows.net",\n'
                f'    credential=credential\n'
                f')\n\n'
                f'# Or use AzCopy with EXP tenant login:\n'
                f'# azcopy login --tenant-id {TARGET_M365_TENANT["tenant_id"]}\n'
                f'# azcopy copy "https://<src>.blob.core.windows.net/bronze" \\\n'
                f'#   "https://<dst>.blob.core.windows.net/{target}" --recursive\n'
            ),
            "sharepoint": (
                f'# Use ADF SharePoint connector\n'
                f'# Linked Service: SharePoint Online\n'
                f'# Site URL: {location}\n'
                f'# Dataset: SharePoint file or list\n'
                f'# Sink: Azure SQL / Blob / ADLS → {target}\n'
            ),
            "dataverse": (
                f'# Use Synapse Link for Dataverse (continuous sync)\n'
                f'# 1. Power Platform Admin → Synapse Link → New link\n'
                f'# 2. Select tables from {location}\n'
                f'# 3. Connect to ADLS Gen2 storage\n'
                f'# 4. Query via Synapse serverless SQL\n'
            ),
        }
        return snippets.get(source_type, f"# Custom ingestion needed for source_type='{source_type}'")
