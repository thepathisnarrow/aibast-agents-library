"""
Purview Data Governance Agent — demonstrates Microsoft Purview's unified data
governance capabilities: data catalog, data map, business glossaries, data quality,
data estate health, and federated governance across multi-cloud data estates.

Scenarios for customer demos:
  1. Data Map — discover and classify assets across Azure, Fabric, AWS, GCP, on-prem
  2. Data Catalog — self-service data discovery for analysts and engineers
  3. Business Glossary — standardize terminology and link to physical assets
  4. Data Quality — define rules, monitor scores, track trends
  5. Data Estate Health — unified view of governance coverage and gaps
  6. Data Products — package curated datasets for consumption
  7. Federated governance — domain-based ownership with central policies
  8. Data Classification — Activity Explorer, Content Explorer, Data Explorer
  9. Data Lifecycle Management — retention policies and lifecycle automation
  10. Records Management — retention labels, file plans, disposition reviews

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES, get_purview_auth_preamble


# ── Data Governance domains and capabilities ───────────────────────────────

GOVERNANCE_DOMAINS = {
    "finance": {"steward": "CFO Office", "assets": ["GL accounts", "financial statements", "budgets"]},
    "sales": {"steward": "Revenue Operations", "assets": ["opportunities", "pipeline", "quotas"]},
    "hr": {"steward": "People Analytics", "assets": ["employee records", "compensation", "org structure"]},
    "supply_chain": {"steward": "Operations", "assets": ["inventory", "suppliers", "logistics"]},
    "customer": {"steward": "Customer Success", "assets": ["accounts", "contacts", "support tickets"]},
    "product": {"steward": "Product Management", "assets": ["telemetry", "feature flags", "usage metrics"]},
}

DATA_QUALITY_RULE_TYPES = {
    "freshness": "Data was updated within the expected time window",
    "completeness": "Required fields are not null/empty",
    "uniqueness": "Primary key values are unique (no duplicates)",
    "accuracy": "Values fall within valid ranges or match reference data",
    "consistency": "Same entity has consistent values across systems",
    "conformity": "Data matches expected format (regex, enum, schema)",
}

DATA_PRODUCT_TEMPLATE = {
    "name": "",
    "description": "",
    "domain": "",
    "owner": "",
    "sla": {"freshness": "daily", "quality_score_min": 95},
    "assets": [],
    "access_policy": "request-based",
    "documentation_url": "",
}

HEALTH_SCORE_DIMENSIONS = [
    {"dimension": "Discovery", "description": "% of data assets registered in Purview", "weight": 0.2},
    {"dimension": "Classification", "description": "% of assets with sensitivity labels applied", "weight": 0.2},
    {"dimension": "Ownership", "description": "% of assets with assigned owners/stewards", "weight": 0.2},
    {"dimension": "Quality", "description": "Average data quality score across monitored assets", "weight": 0.2},
    {"dimension": "Glossary Coverage", "description": "% of key terms linked to physical assets", "weight": 0.1},
    {"dimension": "Lineage", "description": "% of assets with documented upstream/downstream lineage", "weight": 0.1},
]

DATA_CLASSIFICATION_EXPLORERS = {
    "activity_explorer": {
        "description": "Monitor labeling, DLP, and sharing activities across the tenant",
        "insights": ["Label applied/changed/removed events", "DLP rule matches", "Sharing events for labeled content"],
    },
    "content_explorer": {
        "description": "Browse actual content that matches sensitive info types or has labels",
        "insights": ["View items matching SITs", "Preview labeled content", "Assess classification accuracy"],
    },
    "data_explorer": {
        "description": "Explore data assets and their classification status at scale",
        "insights": ["Classification coverage gaps", "Unclassified sensitive data", "Label distribution by workload"],
    },
}

RETENTION_POLICY_TEMPLATES = {
    "regulatory_7yr": {
        "name": "Regulatory — 7 Year Retention",
        "retain_days": 2555,
        "delete_after": True,
        "locations": ["Exchange", "SharePoint", "OneDrive", "Teams"],
        "use_case": "Financial services, healthcare, SOX compliance",
    },
    "litigation_hold": {
        "name": "Litigation Hold — Indefinite",
        "retain_days": None,
        "delete_after": False,
        "locations": ["Exchange", "SharePoint", "OneDrive", "Teams"],
        "use_case": "Active litigation, regulatory investigation",
    },
    "project_lifecycle": {
        "name": "Project Lifecycle — 1 Year After Closure",
        "retain_days": 365,
        "delete_after": True,
        "locations": ["SharePoint", "Teams"],
        "use_case": "Project-based work with defined closure dates",
    },
    "ephemeral_comms": {
        "name": "Ephemeral Communications — 30 Days",
        "retain_days": 30,
        "delete_after": True,
        "locations": ["Teams Chat"],
        "use_case": "Non-record communications, reducing data sprawl",
    },
}

RECORDS_MANAGEMENT_CAPABILITIES = {
    "retention_labels": "Declare items as records with specific retention periods",
    "file_plan": "Structured framework mapping regulatory requirements to retention labels",
    "disposition_review": "Multi-stage review before content is permanently deleted",
    "regulatory_records": "Immutable records that cannot be edited or deleted until retention expires",
    "event_based_retention": "Trigger retention based on business events (e.g., contract expiry)",
}


class PurviewDataGovernanceAgent(BasicAgent):
    """Demonstrates Microsoft Purview unified data governance across the data estate."""

    def __init__(self):
        self.name = "PurviewDataGovernance"
        self.metadata = {
            "name": self.name,
            "description": (
                "Demonstrates Microsoft Purview data governance: data map, catalog, "
                "business glossary, data quality rules and monitoring, data products, "
                "data estate health scoring, federated governance with domain ownership, "
                "data classification (Activity/Content/Data Explorer), data lifecycle "
                "management, and records management. Generates scripts for Purview REST APIs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "scan_data_estate",
                            "create_collection",
                            "glossary_term",
                            "data_quality_rule",
                            "data_product",
                            "health_score",
                            "domain_governance",
                            "data_classification",
                            "data_lifecycle",
                            "records_management",
                            "demo_scenario",
                            "status",
                        ],
                        "description": (
                            "'scan_data_estate' — register and scan sources to build the data map; "
                            "'create_collection' — organize assets into collections/domains; "
                            "'glossary_term' — create or manage business glossary terms; "
                            "'data_quality_rule' — define data quality rules and monitoring; "
                            "'data_product' — package curated data as a governed data product; "
                            "'health_score' — calculate data estate health across dimensions; "
                            "'domain_governance' — set up federated governance with domain owners; "
                            "'data_classification' — explore classification via Activity/Content/Data Explorer; "
                            "'data_lifecycle' — manage data lifecycle with retention policies; "
                            "'records_management' — retention labels, file plans, disposition reviews; "
                            "'demo_scenario' — build customer demo showing governance value; "
                            "'status' — current governance agent capabilities."
                        ),
                    },
                    "domain": {
                        "type": "string",
                        "enum": ["finance", "sales", "hr", "supply_chain", "customer", "product"],
                        "description": "Business domain for the governance action.",
                    },
                    "purview_account": {
                        "type": "string",
                        "description": "Purview account name (e.g. 'contoso-purview').",
                    },
                    "assets": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Assets to govern (tables, files, collections).",
                    },
                    "quality_rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string", "enum": list(DATA_QUALITY_RULE_TYPES.keys())},
                                "target": {"type": "string"},
                                "threshold": {"type": "number"},
                            },
                        },
                        "description": "Data quality rules to create or evaluate.",
                    },
                    "retention_template": {
                        "type": "string",
                        "enum": list(RETENTION_POLICY_TEMPLATES.keys()),
                        "description": "Retention policy template for data lifecycle or records management.",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "status")

        if action == "health_score":
            return self._health_score()
        elif action == "data_quality_rule":
            return self._data_quality(kwargs.get("quality_rules", []))
        elif action == "domain_governance":
            return self._domain_governance(kwargs.get("domain", "finance"))
        elif action == "data_product":
            return self._data_product(kwargs.get("domain", "sales"))
        elif action == "scan_data_estate":
            return self._scan_data_estate(kwargs.get("purview_account", "contoso-purview"))
        elif action == "data_classification":
            return self._data_classification()
        elif action == "data_lifecycle":
            return self._data_lifecycle(kwargs.get("retention_template", "regulatory_7yr"))
        elif action == "records_management":
            return self._records_management()
        elif action == "demo_scenario":
            return self._demo_scenario()
        elif action == "status":
            return self._status()
        else:
            return json.dumps({
                "action": action,
                "message": f"Action '{action}' acknowledged. Would call Purview Governance APIs.",
                "api_base": f"https://{kwargs.get('purview_account', 'contoso-purview')}.purview.azure.com",
            }, indent=2)

    def _health_score(self):
        return json.dumps({
            "title": "Data Estate Health Score",
            "description": "Composite score showing governance maturity across 6 dimensions.",
            "dimensions": HEALTH_SCORE_DIMENSIONS,
            "interpretation": {
                "90-100": "Excellent — Well-governed estate, minimal risk",
                "70-89": "Good — Most assets governed, some gaps to address",
                "50-69": "Fair — Significant governance gaps, prioritize improvement",
                "0-49": "Needs Attention — Major risks from ungoverned data",
            },
            "improvement_actions": [
                "Run full scans on unregistered data sources",
                "Enable auto-classification for newly ingested data",
                "Assign owners to orphaned assets via domain stewards",
                "Create data quality rules for critical business tables",
            ],
        }, indent=2)

    def _data_quality(self, rules):
        return json.dumps({
            "title": "Data Quality Rules",
            "available_rule_types": DATA_QUALITY_RULE_TYPES,
            "rules_provided": rules if rules else "No rules provided — use 'quality_rules' parameter",
            "monitoring": {
                "schedule": "Daily at 06:00 UTC (configurable)",
                "alerting": "Azure Monitor alerts on score drops below threshold",
                "trending": "Quality scores tracked over time in Purview portal",
            },
            "api_example": (
                f"{get_purview_auth_preamble('contoso-purview')}\n"
                f"# Create a data quality rule\n"
                f"rule = {{\n"
                f"  'name': 'CustomerEmail_Completeness',\n"
                f"  'type': 'completeness',\n"
                f"  'target': 'gold_customers.email',\n"
                f"  'threshold': 99.0\n"
                f"}}\n"
            ),
        }, indent=2)

    def _domain_governance(self, domain):
        domain_info = GOVERNANCE_DOMAINS.get(domain, GOVERNANCE_DOMAINS["finance"])
        return json.dumps({
            "title": f"Federated Governance — {domain.title()} Domain",
            "domain": domain,
            "steward": domain_info["steward"],
            "typical_assets": domain_info["assets"],
            "governance_model": {
                "central_team": "Sets policies, standards, and platform guardrails",
                "domain_steward": "Owns data quality, glossary terms, and access for their domain",
                "data_producers": "Responsible for data freshness and schema stability",
                "data_consumers": "Request access, provide quality feedback",
            },
            "setup_steps": [
                f"1. Create Purview collection for '{domain}' domain",
                f"2. Assign '{domain_info['steward']}' as collection admin",
                f"3. Move domain assets into the collection",
                f"4. Define domain-specific glossary terms",
                f"5. Set data quality rules owned by the domain steward",
                f"6. Configure access policies (who can discover vs. read vs. write)",
            ],
        }, indent=2)

    def _data_product(self, domain):
        return json.dumps({
            "title": f"Data Product — {domain.title()} Domain",
            "template": DATA_PRODUCT_TEMPLATE,
            "description": (
                "A Data Product is a curated, governed dataset published for consumption. "
                "It has an owner, SLA, quality guarantees, and access policies."
            ),
            "example": {
                "name": f"{domain}_360_view",
                "description": f"Curated 360° view of {domain} data — joins across source systems",
                "domain": domain,
                "owner": GOVERNANCE_DOMAINS.get(domain, {}).get("steward", "Data Team"),
                "sla": {"freshness": "daily", "quality_score_min": 95},
                "access_policy": "request-based with auto-approval for domain members",
            },
        }, indent=2)

    def _scan_data_estate(self, purview_account):
        return json.dumps({
            "title": "Scan Data Estate",
            "purview_account": purview_account,
            "supported_sources": [
                "Microsoft Fabric (Lakehouse, Warehouse, KQL Database)",
                "Azure SQL Database / Managed Instance",
                "Azure Data Lake Storage Gen2",
                "Azure Synapse Analytics",
                "Power BI",
                "Amazon S3", "Google BigQuery", "Snowflake",
                "SQL Server (on-premises via SHIR)",
                "SAP, Oracle, Teradata (via connectors)",
            ],
            "api_script": (
                f"{get_purview_auth_preamble(purview_account)}\n"
                f"# List registered sources\n"
                f"sources_url = 'https://{purview_account}.purview.azure.com/scan/datasources?api-version=2023-09-01'\n"
                f"response = requests.get(sources_url, headers=headers)\n"
                f"sources = response.json()\n"
            ),
        }, indent=2)

    def _demo_scenario(self):
        return json.dumps({
            "title": "Data Governance Demo Scenario",
            "scenario_steps": [
                "1. Show the Data Map — all assets discovered across Fabric + Azure + multi-cloud",
                "2. Browse the Data Catalog — search for 'customer' → find all related assets",
                "3. Open an asset → show classifications, lineage, quality score, glossary links",
                "4. Business Glossary — show how 'Revenue' is defined and which assets contain it",
                "5. Data Quality — show a quality rule firing on a null-email check",
                "6. Data Products — show a curated dataset with SLA and access request workflow",
                "7. Health Score — show the exec dashboard with governance coverage %",
            ],
            "value_proposition": [
                "Find data faster — self-service catalog eliminates 'ask around' culture",
                "Trust data more — quality scores and lineage build confidence",
                "Reduce risk — know what sensitive data exists and who can access it",
                "Scale governance — federated model lets domains own their data",
            ],
        }, indent=2)

    def _data_classification(self):
        return json.dumps({
            "title": "Data Classification — Explorer Tools",
            "description": (
                "Three explorers provide visibility into how data is classified, "
                "labeled, and accessed across your Microsoft 365 environment."
            ),
            "explorers": DATA_CLASSIFICATION_EXPLORERS,
            "key_value": [
                "Activity Explorer — understand how users interact with labeled/sensitive content",
                "Content Explorer — verify classification accuracy by browsing actual matched content",
                "Data Explorer — identify gaps where sensitive data lacks proper classification",
            ],
            "prerequisites": [
                "Content Explorer Content Viewer role for browsing content",
                "Content Explorer List Viewer role for seeing items (without content)",
                "Data classification scanning enabled on workloads",
            ],
        }, indent=2)

    def _data_lifecycle(self, template):
        policy = RETENTION_POLICY_TEMPLATES.get(template, RETENTION_POLICY_TEMPLATES["regulatory_7yr"])
        return json.dumps({
            "title": f"Data Lifecycle Management — {policy['name']}",
            "description": (
                "Data Lifecycle Management automates retention and deletion of content "
                "to meet regulatory, legal, and business requirements."
            ),
            "policy": policy,
            "powershell_script": (
                "Connect-IPPSSession\n\n"
                f"# Create retention policy: {policy['name']}\n"
                f"New-RetentionCompliancePolicy -Name '{policy['name']}' "
                f"-ExchangeLocation All -SharePointLocation All "
                f"-OneDriveLocation All -ModernGroupLocation All\n\n"
                f"# Add retention rule\n"
                f"New-RetentionComplianceRule -Name '{policy['name']} - Rule' "
                f"-Policy '{policy['name']}' "
                + (f"-RetentionDuration {policy['retain_days']} " if policy['retain_days'] else "-RetentionDuration Unlimited ")
                + f"-RetentionComplianceAction {'Delete' if policy['delete_after'] else 'Keep'}\n"
            ),
            "best_practices": [
                "Start with retain-only policies before enabling deletion",
                "Test with a pilot group before org-wide rollout",
                "Document retention rationale for legal/audit review",
                "Use adaptive scopes for dynamic group membership",
            ],
        }, indent=2)

    def _records_management(self):
        return json.dumps({
            "title": "Records Management",
            "description": (
                "Declare content as records with enforced retention, immutable storage, "
                "and multi-stage disposition reviews."
            ),
            "capabilities": RECORDS_MANAGEMENT_CAPABILITIES,
            "workflow": [
                "1. Create a file plan — map regulatory requirements to retention labels",
                "2. Publish retention labels — make them available to users or auto-apply",
                "3. Apply labels — manually, via auto-apply policies, or trainable classifiers",
                "4. Monitor — track label application and retention status",
                "5. Disposition review — multi-stage approval before permanent deletion",
            ],
            "key_features": [
                "Regulatory records — immutable, cannot be edited or deleted",
                "Event-based retention — trigger on contract expiry, employee departure, etc.",
                "File plan descriptors — structured metadata for compliance reporting",
                "Disposition review — multi-reviewer approval workflow before deletion",
                "Proof of disposition — auditable evidence of compliant deletion",
            ],
        }, indent=2)

    def _status(self):
        return json.dumps({
            "agent": self.name,
            "domains": list(GOVERNANCE_DOMAINS.keys()),
            "quality_rule_types": list(DATA_QUALITY_RULE_TYPES.keys()),
            "health_dimensions": len(HEALTH_SCORE_DIMENSIONS),
            "classification_explorers": list(DATA_CLASSIFICATION_EXPLORERS.keys()),
            "retention_templates": list(RETENTION_POLICY_TEMPLATES.keys()),
            "records_capabilities": list(RECORDS_MANAGEMENT_CAPABILITIES.keys()),
            "tenant": TARGET_M365_TENANT["tenant_id"],
            "purview_portal": "https://purview.microsoft.com",
        }, indent=2)
