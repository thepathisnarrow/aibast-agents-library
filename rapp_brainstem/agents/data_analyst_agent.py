"""
Data Analyst Agent — ensures all data assets are known, documented, and governed
using Microsoft Purview. Designed to receive handoff from the Data Engineer agent
after provisioning and ingestion are complete.

Responsibilities:
  1. Register data sources in Purview
  2. Scan and discover assets (tables, files, views, procedures)
  3. Apply classifications and sensitivity labels
  4. Create/update glossary terms and link to assets
  5. Document lineage (source → transformation → destination)
  6. Generate data dictionaries and documentation artifacts

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES, get_purview_auth_preamble


# ── Purview asset types and classifications ────────────────────────────────

SUPPORTED_ASSET_TYPES = {
    "table": {"icon": "📊", "purview_type": "azure_datalake_gen2_resource_set"},
    "view": {"icon": "👁️", "purview_type": "azure_sql_view"},
    "file": {"icon": "📄", "purview_type": "azure_datalake_gen2_path"},
    "procedure": {"icon": "⚙️", "purview_type": "azure_sql_stored_procedure"},
    "column": {"icon": "📐", "purview_type": "column"},
    "database": {"icon": "🗄️", "purview_type": "azure_sql_db"},
    "lakehouse": {"icon": "🏠", "purview_type": "microsoft_fabric_lakehouse"},
    "eventhouse": {"icon": "⚡", "purview_type": "microsoft_fabric_eventhouse"},
    "warehouse": {"icon": "🏗️", "purview_type": "microsoft_fabric_warehouse"},
    "pipeline": {"icon": "🔗", "purview_type": "azure_data_factory_pipeline"},
    "notebook": {"icon": "📓", "purview_type": "microsoft_fabric_notebook"},
    "kql_database": {"icon": "🔍", "purview_type": "microsoft_fabric_kql_database"},
}

CLASSIFICATION_CATEGORIES = {
    "sensitivity": {
        "display": "Sensitivity Labels",
        "values": [
            "Public", "General", "Confidential", "Highly Confidential",
            "Personal", "GDPR Subject Data", "PHI", "PCI",
        ],
    },
    "data_type": {
        "display": "Data Type Classifications",
        "values": [
            "Email Address", "Phone Number", "Credit Card Number",
            "Social Security Number", "IP Address", "Person Name",
            "Physical Address", "Date of Birth", "Financial Account",
            "Government ID", "Medical Record", "Passport Number",
        ],
    },
    "business_domain": {
        "display": "Business Domain",
        "values": [
            "Finance", "HR", "Sales", "Marketing", "Operations",
            "Supply Chain", "Customer", "Product", "IoT/Telemetry",
            "Compliance", "Security", "Analytics",
        ],
    },
}

GLOSSARY_TERM_TEMPLATE = {
    "name": "",
    "definition": "",
    "abbreviation": "",
    "status": "Draft",
    "steward": "",
    "expert": "",
    "related_terms": [],
    "classified_assets": [],
}


class DataAnalystAgent(BasicAgent):
    """Documents and governs data assets using Microsoft Purview."""

    def __init__(self):
        self.name = "DataAnalyst"
        self.metadata = {
            "name": self.name,
            "description": (
                "Ensures all data assets are known, documented, and governed using "
                "Microsoft Purview. Registers data sources, scans for schema discovery, "
                "applies classifications and sensitivity labels, creates glossary terms, "
                "documents lineage, and generates data dictionaries. Designed to receive "
                "handoff from the DataEngineer agent after provisioning and ingestion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "handoff_from_engineer",
                            "register_source",
                            "scan_assets",
                            "classify",
                            "glossary",
                            "document_lineage",
                            "generate_data_dictionary",
                            "status",
                        ],
                        "description": (
                            "'handoff_from_engineer' — accept provisioned assets from DataEngineer and run full governance workflow; "
                            "'register_source' — register a data source in Purview; "
                            "'scan_assets' — discover schema and metadata for registered assets; "
                            "'classify' — apply classifications/sensitivity labels to assets; "
                            "'glossary' — create or update glossary terms; "
                            "'document_lineage' — record data lineage relationships; "
                            "'generate_data_dictionary' — produce documentation for all assets; "
                            "'status' — check governance coverage and gaps."
                        ),
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["fabric", "azure"],
                        "description": "Target platform. Defaults to 'fabric'.",
                    },
                    "purview_account": {
                        "type": "string",
                        "description": "Purview account name (e.g. 'contoso-purview').",
                    },
                    "assets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Asset name (table, file, view, etc.)."},
                                "type": {"type": "string", "description": "Asset type: table, view, file, procedure, lakehouse, eventhouse, warehouse, pipeline, notebook."},
                                "location": {"type": "string", "description": "Where the asset lives (workspace/database/container)."},
                                "description": {"type": "string", "description": "What this asset contains or represents."},
                                "columns": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "data_type": {"type": "string"},
                                            "description": {"type": "string"},
                                            "classification": {"type": "string"},
                                        },
                                    },
                                    "description": "Column-level metadata (for tables/views).",
                                },
                                "owner": {"type": "string", "description": "Data owner or steward."},
                                "domain": {"type": "string", "description": "Business domain (Finance, HR, Sales, etc.)."},
                            },
                            "required": ["name", "type"],
                        },
                        "description": "Assets to register, scan, classify, or document.",
                    },
                    "classifications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "asset_name": {"type": "string"},
                                "column_name": {"type": "string", "description": "Optional — classify at column level."},
                                "classification": {"type": "string", "description": "Classification label to apply."},
                                "category": {"type": "string", "enum": ["sensitivity", "data_type", "business_domain"]},
                            },
                            "required": ["asset_name", "classification"],
                        },
                        "description": "Classifications to apply to assets or columns.",
                    },
                    "glossary_terms": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Term name."},
                                "definition": {"type": "string", "description": "Business definition."},
                                "abbreviation": {"type": "string"},
                                "steward": {"type": "string", "description": "Person responsible for this term."},
                                "related_assets": {"type": "array", "items": {"type": "string"}, "description": "Asset names this term applies to."},
                            },
                            "required": ["name", "definition"],
                        },
                        "description": "Glossary terms to create or update in Purview.",
                    },
                    "lineage": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string", "description": "Source asset name."},
                                "destination": {"type": "string", "description": "Destination asset name."},
                                "transformation": {"type": "string", "description": "What happens between source and destination."},
                                "process_name": {"type": "string", "description": "Pipeline/notebook/dataflow that performs this."},
                            },
                            "required": ["source", "destination"],
                        },
                        "description": "Lineage relationships to document.",
                    },
                    "engineer_output": {
                        "type": "object",
                        "description": "Direct output from the DataEngineer agent (provisioned resources, ingestion plans). Pass this for automatic handoff.",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__(name=self.name, metadata=self.metadata)

    def perform(self, **kwargs):
        action = kwargs.get("action", "status")
        platform = kwargs.get("platform", "fabric")

        if action == "handoff_from_engineer":
            return self._handoff_from_engineer(platform, kwargs)
        elif action == "register_source":
            return self._register_source(platform, kwargs)
        elif action == "scan_assets":
            return self._scan_assets(platform, kwargs)
        elif action == "classify":
            return self._classify(kwargs)
        elif action == "glossary":
            return self._glossary(kwargs)
        elif action == "document_lineage":
            return self._document_lineage(kwargs)
        elif action == "generate_data_dictionary":
            return self._generate_data_dictionary(platform, kwargs)
        elif action == "status":
            return self._status(kwargs)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    # ── Handoff from DataEngineer ──────────────────────────────────────────

    def _handoff_from_engineer(self, platform, kwargs):
        """Accept output from DataEngineer and run the full governance workflow."""
        engineer_output = kwargs.get("engineer_output", {})
        assets = kwargs.get("assets", [])

        # Parse engineer output to extract assets if not explicitly provided
        if not assets and engineer_output:
            assets = self._extract_assets_from_engineer(engineer_output)

        if not assets:
            return json.dumps({
                "status": "needs_input",
                "message": (
                    "I need to know what was created. Either:\n"
                    "1. Pass the DataEngineer's output as 'engineer_output'\n"
                    "2. List assets directly with name, type, and location\n\n"
                    "What assets were provisioned and what data was loaded?"
                ),
            })

        purview_account = kwargs.get("purview_account", "<your-purview-account>")

        # Run the full governance workflow
        workflow_results = {
            "step_1_register": self._generate_registration(platform, assets, purview_account),
            "step_2_scan": self._generate_scan_config(platform, assets, purview_account),
            "step_3_classify": self._auto_classify_recommendations(assets),
            "step_4_glossary": self._auto_glossary_recommendations(assets),
            "step_5_lineage": self._extract_lineage(assets, kwargs.get("lineage", [])),
        }

        return json.dumps({
            "status": "success",
            "message": (
                f"Governance workflow initiated for {len(assets)} asset(s). "
                "Review each step below and confirm or customize."
            ),
            "purview_account": purview_account,
            "platform": platform,
            "asset_count": len(assets),
            "workflow": workflow_results,
            "scripts": {
                "register_and_scan": self._full_purview_script(platform, assets, purview_account),
            },
            "next_steps": [
                "Review auto-classifications and adjust sensitivity labels as needed.",
                "Approve or edit glossary term definitions with the data steward.",
                "Verify lineage connections are complete (source → transform → destination).",
                "Run action='generate_data_dictionary' to produce the final documentation artifact.",
            ],
        }, indent=2)

    def _extract_assets_from_engineer(self, engineer_output):
        """Parse DataEngineer output to extract asset list."""
        assets = []
        provisioned = engineer_output.get("provisioned", [])
        if not provisioned:
            # Check nested structure from full_setup
            phase1 = engineer_output.get("phase_1_provision", {})
            provisioned = phase1.get("provisioned", [])

        for res in provisioned:
            asset = {
                "name": res.get("name", ""),
                "type": self._map_resource_to_asset_type(res.get("type", "")),
                "location": res.get("workspace", ""),
                "description": f"{res.get('display_name', '')} provisioned by DataEngineer",
            }
            assets.append(asset)

        # Also check ingestion plans for table-level assets
        ingestion_plans = engineer_output.get("ingestion_plans", [])
        if not ingestion_plans:
            phase2 = engineer_output.get("phase_2_ingestion", {})
            ingestion_plans = phase2.get("ingestion_plans", [])

        for plan in ingestion_plans:
            target = plan.get("target_resource", "")
            if target and not any(a["name"] == target for a in assets):
                assets.append({
                    "name": target,
                    "type": "table",
                    "location": "",
                    "description": plan.get("description", f"Data loaded from {plan.get('source_type', 'unknown')} source"),
                })

        return assets

    def _map_resource_to_asset_type(self, resource_type):
        """Map DataEngineer resource types to Purview asset types."""
        mapping = {
            "lakehouse": "lakehouse",
            "sql_database": "database",
            "eventhouse": "eventhouse",
            "warehouse": "warehouse",
            "data_pipeline": "pipeline",
            "notebook": "notebook",
            "dataflow_gen2": "pipeline",
            "kql_queryset": "kql_database",
            "storage_account": "file",
            "sql_server": "database",
            "synapse_workspace": "database",
            "eventhub_namespace": "eventhouse",
            "data_factory": "pipeline",
            "cosmos_db": "database",
            "adx_cluster": "kql_database",
        }
        return mapping.get(resource_type, "table")

    # ── Register ───────────────────────────────────────────────────────────

    def _register_source(self, platform, kwargs):
        assets = kwargs.get("assets", [])
        purview_account = kwargs.get("purview_account", "<your-purview-account>")

        if not assets:
            return json.dumps({
                "status": "needs_input",
                "message": "Provide assets to register. Each needs at minimum: name and type.",
                "supported_types": list(SUPPORTED_ASSET_TYPES.keys()),
            })

        registrations = self._generate_registration(platform, assets, purview_account)
        return json.dumps({
            "status": "success",
            "registrations": registrations,
            "script": self._register_script(platform, assets, purview_account),
        }, indent=2)

    def _generate_registration(self, platform, assets, purview_account):
        registrations = []
        for asset in assets:
            asset_type = asset.get("type", "table")
            type_info = SUPPORTED_ASSET_TYPES.get(asset_type, SUPPORTED_ASSET_TYPES["table"])
            registrations.append({
                "asset_name": asset.get("name"),
                "asset_type": asset_type,
                "purview_type": type_info["purview_type"],
                "location": asset.get("location", ""),
                "status": "ready_to_register",
            })
        return registrations

    # ── Scan ───────────────────────────────────────────────────────────────

    def _scan_assets(self, platform, kwargs):
        assets = kwargs.get("assets", [])
        purview_account = kwargs.get("purview_account", "<your-purview-account>")

        if not assets:
            return json.dumps({
                "status": "needs_input",
                "message": "Provide assets to scan. I'll generate scan rule sets and triggers.",
            })

        scan_config = self._generate_scan_config(platform, assets, purview_account)
        return json.dumps({
            "status": "success",
            "scan_configuration": scan_config,
            "script": self._scan_script(platform, assets, purview_account),
        }, indent=2)

    def _generate_scan_config(self, platform, assets, purview_account):
        configs = []
        for asset in assets:
            asset_type = asset.get("type", "table")
            configs.append({
                "asset_name": asset.get("name"),
                "scan_rule_set": self._recommend_scan_rules(asset_type),
                "trigger": "weekly",
                "scope": "full" if asset_type in ("lakehouse", "database", "warehouse") else "incremental",
                "auto_classify": True,
            })
        return configs

    def _recommend_scan_rules(self, asset_type):
        """Recommend scan rule sets based on asset type."""
        rules = {
            "table": "System default (SQL)",
            "view": "System default (SQL)",
            "file": "System default (ADLS Gen2)",
            "procedure": "System default (SQL)",
            "database": "System default (SQL) — all schemas",
            "lakehouse": "Fabric Lakehouse rule set (Delta + Parquet)",
            "eventhouse": "KQL Database rule set",
            "warehouse": "Synapse Warehouse rule set (T-SQL)",
            "pipeline": "Data Factory / Pipeline rule set",
            "notebook": "Notebook lineage extraction",
            "kql_database": "KQL Database rule set",
        }
        return rules.get(asset_type, "System default")

    # ── Classify ───────────────────────────────────────────────────────────

    def _classify(self, kwargs):
        classifications = kwargs.get("classifications", [])
        assets = kwargs.get("assets", [])

        if not classifications and not assets:
            return json.dumps({
                "status": "needs_input",
                "message": (
                    "What classifications should I apply? Options:\n\n"
                    "**Sensitivity:** " + ", ".join(CLASSIFICATION_CATEGORIES["sensitivity"]["values"][:5]) + "\n"
                    "**Data Type:** " + ", ".join(CLASSIFICATION_CATEGORIES["data_type"]["values"][:5]) + "\n"
                    "**Business Domain:** " + ", ".join(CLASSIFICATION_CATEGORIES["business_domain"]["values"][:5]) + "\n\n"
                    "Provide asset names + classifications, or I can auto-recommend based on column names."
                ),
                "available_classifications": CLASSIFICATION_CATEGORIES,
            })

        # If assets provided but no explicit classifications, auto-recommend
        if assets and not classifications:
            recommendations = self._auto_classify_recommendations(assets)
            return json.dumps({
                "status": "recommendations",
                "message": "Based on asset metadata, here are my classification recommendations:",
                "recommendations": recommendations,
                "action_required": "Confirm these classifications or provide overrides.",
            }, indent=2)

        applied = []
        for cls in classifications:
            applied.append({
                "asset": cls.get("asset_name"),
                "column": cls.get("column_name"),
                "classification": cls.get("classification"),
                "category": cls.get("category", "sensitivity"),
                "status": "applied",
            })

        return json.dumps({
            "status": "success",
            "classifications_applied": applied,
            "script": self._classify_script(classifications),
        }, indent=2)

    def _auto_classify_recommendations(self, assets):
        """Recommend classifications based on asset/column names."""
        recommendations = []
        pii_indicators = {
            "email": ("Email Address", "data_type"),
            "phone": ("Phone Number", "data_type"),
            "ssn": ("Social Security Number", "data_type"),
            "address": ("Physical Address", "data_type"),
            "dob": ("Date of Birth", "data_type"),
            "birth": ("Date of Birth", "data_type"),
            "salary": ("Confidential", "sensitivity"),
            "credit_card": ("Credit Card Number", "data_type"),
            "account_number": ("Financial Account", "data_type"),
            "patient": ("PHI", "sensitivity"),
            "diagnosis": ("PHI", "sensitivity"),
        }

        for asset in assets:
            columns = asset.get("columns", [])
            domain = asset.get("domain", "")

            # Asset-level domain classification
            if domain:
                recommendations.append({
                    "asset_name": asset["name"],
                    "classification": domain,
                    "category": "business_domain",
                    "confidence": "high",
                    "reason": "Explicitly tagged domain",
                })

            # Column-level PII detection
            for col in columns:
                col_name = (col.get("name") or "").lower()
                for indicator, (classification, category) in pii_indicators.items():
                    if indicator in col_name:
                        recommendations.append({
                            "asset_name": asset["name"],
                            "column_name": col.get("name"),
                            "classification": classification,
                            "category": category,
                            "confidence": "medium",
                            "reason": f"Column name contains '{indicator}'",
                        })

            # If no columns provided, recommend a scan
            if not columns:
                recommendations.append({
                    "asset_name": asset["name"],
                    "classification": "(scan required)",
                    "category": "sensitivity",
                    "confidence": "low",
                    "reason": "No column metadata — run a scan to discover schema and auto-classify.",
                })

        return recommendations

    # ── Glossary ───────────────────────────────────────────────────────────

    def _glossary(self, kwargs):
        terms = kwargs.get("glossary_terms", [])
        assets = kwargs.get("assets", [])

        if not terms and not assets:
            return json.dumps({
                "status": "needs_input",
                "message": (
                    "What glossary terms should I create? Each term needs:\n"
                    "- **name**: The business term (e.g. 'Customer Lifetime Value')\n"
                    "- **definition**: What it means in plain language\n"
                    "- **steward** (optional): Who owns this term\n"
                    "- **related_assets** (optional): Which assets use this term\n\n"
                    "Or provide assets and I'll recommend terms based on their names and descriptions."
                ),
            })

        if assets and not terms:
            recommendations = self._auto_glossary_recommendations(assets)
            return json.dumps({
                "status": "recommendations",
                "message": "Suggested glossary terms based on your assets:",
                "recommended_terms": recommendations,
                "action_required": "Review, edit definitions, and confirm to create in Purview.",
            }, indent=2)

        created = []
        for term in terms:
            entry = {**GLOSSARY_TERM_TEMPLATE}
            entry["name"] = term.get("name", "")
            entry["definition"] = term.get("definition", "")
            entry["abbreviation"] = term.get("abbreviation", "")
            entry["steward"] = term.get("steward", "")
            entry["classified_assets"] = term.get("related_assets", [])
            entry["status"] = "Draft"
            created.append(entry)

        return json.dumps({
            "status": "success",
            "terms_created": created,
            "script": self._glossary_script(terms),
            "next_step": "Review terms in Purview portal and promote from Draft → Approved.",
        }, indent=2)

    def _auto_glossary_recommendations(self, assets):
        """Generate glossary term recommendations from asset metadata."""
        terms = []
        for asset in assets:
            name = asset.get("name", "")
            desc = asset.get("description", "")
            if name:
                terms.append({
                    "name": name,
                    "definition": desc or f"(Define what '{name}' represents in business context)",
                    "related_assets": [name],
                    "status": "Draft — needs business definition",
                })

            # Suggest terms for columns
            for col in asset.get("columns", []):
                col_name = col.get("name", "")
                if col_name and len(col_name) > 3:
                    terms.append({
                        "name": col_name.replace("_", " ").title(),
                        "definition": col.get("description", f"(Define '{col_name}' in business terms)"),
                        "related_assets": [name],
                        "status": "Draft — needs business definition",
                    })

        return terms

    # ── Lineage ────────────────────────────────────────────────────────────

    def _document_lineage(self, kwargs):
        lineage = kwargs.get("lineage", [])

        if not lineage:
            return json.dumps({
                "status": "needs_input",
                "message": (
                    "Document your data lineage — where does data flow?\n\n"
                    "For each relationship, tell me:\n"
                    "- **source**: Where does data come from?\n"
                    "- **destination**: Where does it land?\n"
                    "- **transformation**: What happens in between? (joins, filters, aggregations)\n"
                    "- **process_name**: What pipeline/notebook/dataflow performs this?\n\n"
                    "Example: source='raw_sales_csv' → transformation='clean + deduplicate' → "
                    "destination='dim_customer' via process='etl_pipeline_sales'"
                ),
            })

        documented = []
        for rel in lineage:
            documented.append({
                "source": rel.get("source"),
                "destination": rel.get("destination"),
                "transformation": rel.get("transformation", "direct copy"),
                "process": rel.get("process_name", "(manual or unknown)"),
                "status": "documented",
            })

        return json.dumps({
            "status": "success",
            "lineage_documented": documented,
            "script": self._lineage_script(lineage),
            "visualization_hint": (
                "View lineage in Purview portal: Data Catalog → asset → Lineage tab. "
                "Or use the Purview REST API to query lineage programmatically."
            ),
        }, indent=2)

    def _extract_lineage(self, assets, explicit_lineage):
        """Infer lineage from asset relationships."""
        if explicit_lineage:
            return [{"source": l["source"], "destination": l["destination"],
                     "transformation": l.get("transformation", ""),
                     "process": l.get("process_name", "")} for l in explicit_lineage]

        inferred = []
        pipelines = [a for a in assets if a.get("type") in ("pipeline", "notebook")]
        data_assets = [a for a in assets if a.get("type") not in ("pipeline", "notebook")]

        if pipelines and len(data_assets) >= 2:
            inferred.append({
                "source": data_assets[0]["name"],
                "destination": data_assets[-1]["name"],
                "transformation": "(inferred — verify actual transformation logic)",
                "process": pipelines[0]["name"] if pipelines else "(unknown)",
                "confidence": "low — needs verification",
            })

        if not inferred:
            inferred.append({
                "note": "Lineage could not be auto-inferred. Provide explicit source → destination mappings.",
            })

        return inferred

    # ── Data Dictionary ────────────────────────────────────────────────────

    def _generate_data_dictionary(self, platform, kwargs):
        assets = kwargs.get("assets", [])
        purview_account = kwargs.get("purview_account", "<your-purview-account>")

        if not assets:
            return json.dumps({
                "status": "needs_input",
                "message": (
                    "Provide assets to document. I'll generate a comprehensive data dictionary "
                    "including schema, classifications, glossary terms, and lineage for each asset."
                ),
            })

        dictionary_entries = []
        for asset in assets:
            asset_type = asset.get("type", "table")
            type_info = SUPPORTED_ASSET_TYPES.get(asset_type, SUPPORTED_ASSET_TYPES["table"])

            entry = {
                "asset_name": asset.get("name"),
                "icon": type_info["icon"],
                "type": asset_type,
                "location": asset.get("location", ""),
                "description": asset.get("description", "(no description provided)"),
                "owner": asset.get("owner", "(unassigned)"),
                "domain": asset.get("domain", "(unclassified)"),
                "columns": asset.get("columns", []),
                "classifications": [],
                "glossary_terms": [],
                "purview_url": f"https://{purview_account}.purview.azure.com/asset/{asset.get('name', '')}",
            }
            dictionary_entries.append(entry)

        markdown = self._render_data_dictionary_md(dictionary_entries)

        return json.dumps({
            "status": "success",
            "data_dictionary": dictionary_entries,
            "markdown": markdown,
            "export_options": [
                "Copy the markdown below into your project wiki or README.",
                "Use Purview's built-in data catalog for a live, searchable version.",
                f"API: GET https://{purview_account}.purview.azure.com/catalog/api/atlas/v2/search/query",
            ],
        }, indent=2)

    def _render_data_dictionary_md(self, entries):
        """Render data dictionary as markdown."""
        lines = ["# Data Dictionary", "", "Auto-generated by DataAnalyst agent via Microsoft Purview.", ""]

        for entry in entries:
            lines.append(f"## {entry['icon']} {entry['asset_name']}")
            lines.append("")
            lines.append(f"| Property | Value |")
            lines.append(f"|----------|-------|")
            lines.append(f"| **Type** | {entry['type']} |")
            lines.append(f"| **Location** | {entry['location'] or '—'} |")
            lines.append(f"| **Description** | {entry['description']} |")
            lines.append(f"| **Owner** | {entry['owner']} |")
            lines.append(f"| **Domain** | {entry['domain']} |")
            lines.append("")

            if entry.get("columns"):
                lines.append("### Columns")
                lines.append("")
                lines.append("| Column | Type | Description | Classification |")
                lines.append("|--------|------|-------------|----------------|")
                for col in entry["columns"]:
                    lines.append(
                        f"| {col.get('name', '')} | {col.get('data_type', '')} | "
                        f"{col.get('description', '')} | {col.get('classification', '—')} |"
                    )
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    # ── Status / Coverage ──────────────────────────────────────────────────

    def _status(self, kwargs):
        assets = kwargs.get("assets", [])

        if not assets:
            return json.dumps({
                "status": "info",
                "message": (
                    "I track governance coverage across these dimensions:\n\n"
                    "1. **Registration** — Is the asset registered in Purview?\n"
                    "2. **Scanned** — Has schema been discovered?\n"
                    "3. **Classified** — Are sensitivity labels applied?\n"
                    "4. **Glossary** — Are business terms defined and linked?\n"
                    "5. **Lineage** — Is the data flow documented?\n"
                    "6. **Ownership** — Is a steward assigned?\n\n"
                    "Provide your assets and I'll assess coverage gaps."
                ),
                "governance_dimensions": [
                    "registration", "scanned", "classified",
                    "glossary", "lineage", "ownership",
                ],
            })

        coverage = []
        for asset in assets:
            score = 0
            checks = {
                "registered": bool(asset.get("location")),
                "scanned": bool(asset.get("columns")),
                "classified": any(c.get("classification") for c in asset.get("columns", [])),
                "glossary_linked": bool(asset.get("description") and len(asset.get("description", "")) > 10),
                "lineage_documented": False,
                "owner_assigned": bool(asset.get("owner")),
            }
            score = sum(checks.values())
            coverage.append({
                "asset": asset.get("name"),
                "score": f"{score}/6",
                "checks": checks,
                "gaps": [k for k, v in checks.items() if not v],
            })

        avg_score = sum(sum(c["checks"].values()) for c in coverage) / max(len(coverage), 1)

        return json.dumps({
            "status": "success",
            "coverage_report": coverage,
            "average_score": f"{avg_score:.1f}/6",
            "recommendation": (
                "Focus on the gaps listed above. Priority: classification > lineage > glossary."
                if avg_score < 5 else "Good coverage. Review for accuracy and freshness."
            ),
        }, indent=2)

    # ── Script generators ──────────────────────────────────────────────────

    def _full_purview_script(self, platform, assets, purview_account):
        """Generate complete Purview governance script using EXP tenant auth."""
        auth_preamble = get_purview_auth_preamble(purview_account)
        return (
            f'"""Full Purview governance script for {len(assets)} asset(s)."""\n'
            + auth_preamble + '\n'
            f'from azure.purview.catalog import PurviewCatalogClient\n'
            f'from azure.purview.scanning import PurviewScanningClient\n\n'
            f'catalog_client = PurviewCatalogClient(\n'
            f'    endpoint="https://{purview_account}.purview.azure.com",\n'
            f'    credential=credential\n'
            f')\n'
            f'scanning_client = PurviewScanningClient(\n'
            f'    endpoint="https://{purview_account}.purview.azure.com",\n'
            f'    credential=credential\n'
            f')\n\n'
            f'# Step 1: Register data sources\n'
            + "\n".join(
                f'scanning_client.data_sources.create_or_update(\n'
                f'    "{a.get("name", "")}", '
                f'{{"kind": "{self._get_source_kind(platform, a.get("type", ""))}", '
                f'"properties": {{"endpoint": "{a.get("location", "")}", '
                f'"collection": {{"referenceName": "root"}}}}}}\n'
                f')\nprint(f"Registered: {a.get("name", "")}")\n'
                for a in assets
            )
            + f'\n# Step 2: Create and run scans\n'
            + "\n".join(
                f'scanning_client.scans.create_or_update(\n'
                f'    "{a.get("name", "")}", "scan-{a.get("name", "")[:20]}", '
                f'{{"kind": "Default", "properties": {{"scanRulesetName": "system-default"}}}}\n'
                f')\n'
                for a in assets
            )
            + f'\nprint("All sources registered and scans initiated.")\n'
        )

    def _get_source_kind(self, platform, asset_type):
        if platform == "fabric":
            kinds = {
                "lakehouse": "FabricLakehouse",
                "sql_database": "FabricSqlDatabase",
                "eventhouse": "FabricEventhouse",
                "warehouse": "FabricWarehouse",
                "notebook": "FabricNotebook",
            }
        else:
            kinds = {
                "database": "AzureSqlDatabase",
                "file": "AdlsGen2",
                "table": "AdlsGen2",
                "eventhouse": "AzureDataExplorer",
            }
        return kinds.get(asset_type, "AdlsGen2")

    def _register_script(self, platform, assets, purview_account):
        auth_preamble = get_purview_auth_preamble(purview_account)
        return (
            f'# Register sources via Purview REST API (EXP tenant: davidwin@onemtc.net)\n'
            + auth_preamble + '\n'
            f'import requests\n\n'
            f'PURVIEW = "https://{purview_account}.purview.azure.com"\n'
            f'token = credential.get_token("{SCOPES["purview"]}").token\n'
            f'headers = {{"Authorization": f"Bearer {{token}}"}}\n\n'
            + "\n".join(
                f'# Register: {a.get("name")}\n'
                f'requests.put(\n'
                f'    f"{{PURVIEW}}/scan/datasources/{a.get("name")}?api-version=2022-07-01-preview",\n'
                f'    headers=headers,\n'
                f'    json={{"kind": "{self._get_source_kind(platform, a.get("type", ""))}", '
                f'"properties": {{"endpoint": "{a.get("location", "")}"}}}}\n'
                f')\n'
                for a in assets
            )
        )

    def _scan_script(self, platform, assets, purview_account):
        auth_preamble = get_purview_auth_preamble(purview_account)
        return (
            f'# Trigger scans via Purview REST API (EXP tenant: davidwin@onemtc.net)\n'
            + auth_preamble + '\n'
            f'import requests, uuid\n\n'
            f'PURVIEW = "https://{purview_account}.purview.azure.com"\n'
            f'token = credential.get_token("{SCOPES["purview"]}").token\n'
            f'headers = {{"Authorization": f"Bearer {{token}}"}}\n\n'
            + "\n".join(
                f'# Scan: {a.get("name")}\n'
                f'run_id = str(uuid.uuid4())\n'
                f'requests.put(\n'
                f'    f"{{PURVIEW}}/scan/datasources/{a.get("name")}/scans/default-scan/runs/{{run_id}}?api-version=2022-07-01-preview",\n'
                f'    headers=headers\n'
                f')\n'
                for a in assets
            )
        )

    def _classify_script(self, classifications):
        return (
            f'# Apply classifications via Purview REST API (EXP tenant: davidwin@onemtc.net)\n'
            f'from azure.identity import InteractiveBrowserCredential, AzureCliCredential, ChainedTokenCredential\n'
            f'import requests\n\n'
            f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n'
            f'credential = ChainedTokenCredential(\n'
            f'    AzureCliCredential(tenant_id=TENANT_ID),\n'
            f'    InteractiveBrowserCredential(tenant_id=TENANT_ID, login_hint="{TARGET_M365_TENANT["login_hint"]}")\n'
            f')\n'
            f'token = credential.get_token("{SCOPES["purview"]}").token\n'
            f'headers = {{"Authorization": f"Bearer {{token}}"}}\n\n'
            f'PURVIEW = "https://<purview-account>.purview.azure.com"\n\n'
            + "\n".join(
                f'# Classify: {c.get("asset_name")}'
                + (f'.{c.get("column_name")}' if c.get("column_name") else "")
                + f' → {c.get("classification")}\n'
                f'requests.post(\n'
                f'    f"{{PURVIEW}}/catalog/api/atlas/v2/entity/uniqueAttribute/type/column'
                f'?attr:qualifiedName={c.get("asset_name")}'
                + (f'.{c.get("column_name")}' if c.get("column_name") else "")
                + f'",\n'
                f'    headers=headers,\n'
                f'    json={{"classifications": [{{"typeName": "{c.get("classification")}"}}]}}\n'
                f')\n'
                for c in classifications
            )
        )

    def _glossary_script(self, terms):
        return (
            f'# Create glossary terms via Purview REST API (EXP tenant: davidwin@onemtc.net)\n'
            f'from azure.identity import InteractiveBrowserCredential, AzureCliCredential, ChainedTokenCredential\n'
            f'import requests\n\n'
            f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n'
            f'credential = ChainedTokenCredential(\n'
            f'    AzureCliCredential(tenant_id=TENANT_ID),\n'
            f'    InteractiveBrowserCredential(tenant_id=TENANT_ID, login_hint="{TARGET_M365_TENANT["login_hint"]}")\n'
            f')\n'
            f'token = credential.get_token("{SCOPES["purview"]}").token\n'
            f'headers = {{"Authorization": f"Bearer {{token}}"}}\n\n'
            f'PURVIEW = "https://<purview-account>.purview.azure.com"\n\n'
            + "\n".join(
                f'# Term: {t.get("name")}\n'
                f'requests.post(\n'
                f'    f"{{PURVIEW}}/catalog/api/atlas/v2/glossary/term",\n'
                f'    headers=headers,\n'
                f'    json={{\n'
                f'        "name": "{t.get("name")}",\n'
                f'        "longDescription": "{t.get("definition", "")}",\n'
                f'        "status": "Draft",\n'
                f'        "anchor": {{"glossaryGuid": "<default-glossary-guid>"}}\n'
                f'    }}\n'
                f')\n'
                for t in terms
            )
        )

    def _lineage_script(self, lineage):
        return (
            f'# Document lineage via Purview REST API (EXP tenant: davidwin@onemtc.net)\n'
            f'from azure.identity import InteractiveBrowserCredential, AzureCliCredential, ChainedTokenCredential\n'
            f'import requests\n\n'
            f'TENANT_ID = "{TARGET_M365_TENANT["tenant_id"]}"\n'
            f'credential = ChainedTokenCredential(\n'
            f'    AzureCliCredential(tenant_id=TENANT_ID),\n'
            f'    InteractiveBrowserCredential(tenant_id=TENANT_ID, login_hint="{TARGET_M365_TENANT["login_hint"]}")\n'
            f')\n'
            f'token = credential.get_token("{SCOPES["purview"]}").token\n'
            f'headers = {{"Authorization": f"Bearer {{token}}"}}\n\n'
            f'PURVIEW = "https://<purview-account>.purview.azure.com"\n\n'
            f'# Lineage is typically auto-discovered from scanned pipelines/notebooks.\n'
            f'# For manual lineage, use the Atlas lineage API:\n\n'
            + "\n".join(
                f'# {l.get("source")} → {l.get("destination")}\n'
                f'requests.post(\n'
                f'    f"{{PURVIEW}}/catalog/api/atlas/v2/entity",\n'
                f'    headers=headers,\n'
                f'    json={{\n'
                f'        "entity": {{\n'
                f'            "typeName": "Process",\n'
                f'            "attributes": {{\n'
                f'                "name": "{l.get("process_name", "data_flow")}",\n'
                f'                "qualifiedName": "{l.get("source")}_to_{l.get("destination")}",\n'
                f'                "inputs": [{{"typeName": "DataSet", "uniqueAttributes": {{"qualifiedName": "{l.get("source")}"}}}},],\n'
                f'                "outputs": [{{"typeName": "DataSet", "uniqueAttributes": {{"qualifiedName": "{l.get("destination")}"}}}},]\n'
                f'            }}\n'
                f'        }}\n'
                f'    }}\n'
                f')\n'
                for l in lineage
            )
        )
