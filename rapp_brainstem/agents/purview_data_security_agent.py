"""
Purview Data Security Agent — demonstrates Microsoft Purview's data security
capabilities: sensitivity labels, DLP policies, encryption, access controls,
and insider risk signals integrated with Microsoft 365.

Scenarios for customer demos:
  1. Sensitivity labeling — auto-label and manual label across M365, Fabric, Azure
  2. Data Loss Prevention (DLP) — policy creation, simulation, incident response
  3. Endpoint DLP — extend protection to devices and local file systems
  4. Encryption & rights management — Azure Information Protection (AIP)
  5. Data Security Investigations — investigate data security incidents end-to-end
  6. Data Security Posture Management (DSPM) — posture insights and recommendations
  7. Exact Data Match (EDM) — custom sensitive info types from structured data

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES


# ── Data Security capabilities ─────────────────────────────────────────────

SENSITIVITY_LABEL_TIERS = [
    {"name": "Public", "color": "#00B050", "protection": "None"},
    {"name": "General", "color": "#0078D4", "protection": "Footer marking"},
    {"name": "General - Anyone (unrestricted)", "color": "#0078D4", "protection": "Footer + Header"},
    {"name": "Confidential", "color": "#FFB900", "protection": "Encryption (org-wide access)"},
    {"name": "Confidential - Anyone (unrestricted)", "color": "#FFB900", "protection": "Marking only"},
    {"name": "Highly Confidential", "color": "#E81123", "protection": "Encryption (named users/groups)"},
    {"name": "Highly Confidential - Project X", "color": "#E81123", "protection": "Encryption + Watermark"},
]

DLP_POLICY_TEMPLATES = {
    "financial": {
        "name": "Financial Data Protection",
        "description": "Prevent sharing of credit card numbers, bank accounts, financial statements",
        "sensitive_info_types": [
            "Credit Card Number", "IBAN", "SWIFT Code",
            "U.S. Bank Account Number", "ABA Routing Number",
        ],
        "locations": ["Exchange", "SharePoint", "OneDrive", "Teams", "Fabric"],
        "actions": ["Block sharing externally", "Notify user", "Generate incident report"],
    },
    "healthcare": {
        "name": "Healthcare (HIPAA)",
        "description": "Protect PHI — patient records, medical IDs, health plan numbers",
        "sensitive_info_types": [
            "U.S. Social Security Number", "Drug Enforcement Agency (DEA) Number",
            "International Classification of Diseases (ICD-9-CM)",
            "International Classification of Diseases (ICD-10-CM)",
            "U.S. Health Insurance Claim Number (HICN)",
        ],
        "locations": ["Exchange", "SharePoint", "OneDrive", "Teams", "Endpoints"],
        "actions": ["Block sharing externally", "Encrypt", "Require justification"],
    },
    "pii": {
        "name": "Personal Information (PII)",
        "description": "Protect personally identifiable information across all workloads",
        "sensitive_info_types": [
            "U.S. Social Security Number", "Passport Number",
            "Driver's License Number", "Email Address", "Phone Number",
            "Physical Address", "Date of Birth",
        ],
        "locations": ["Exchange", "SharePoint", "OneDrive", "Teams", "Fabric", "Endpoints"],
        "actions": ["Policy tip to user", "Block external sharing", "Audit"],
    },
    "custom_fabric": {
        "name": "Fabric Lakehouse Protection",
        "description": "Prevent sensitive data from leaving Microsoft Fabric workspaces",
        "sensitive_info_types": ["Custom — defined by data steward"],
        "locations": ["Fabric"],
        "actions": ["Block download", "Block copy to clipboard", "Audit"],
    },
}

DATA_SECURITY_INVESTIGATIONS_SCENARIOS = {
    "data_exfiltration": {
        "description": "Investigate potential data theft via USB, cloud upload, or email",
        "evidence_sources": ["DLP alerts", "Endpoint activity", "Audit logs", "Insider Risk signals"],
    },
    "oversharing": {
        "description": "Investigate excessive sharing of sensitive content externally",
        "evidence_sources": ["Sharing events", "DLP matches", "Label downgrade events"],
    },
    "compromised_account": {
        "description": "Investigate unauthorized access to sensitive data after credential compromise",
        "evidence_sources": ["Sign-in logs", "File access patterns", "MFA bypass events"],
    },
}

DSPM_CAPABILITIES = {
    "posture_insights": "Visibility into data security posture across M365, Fabric, Azure, multi-cloud",
    "risk_assessment": "Identify overshared, overlabeled, or unprotected sensitive data",
    "recommendations": "Actionable recommendations to reduce data risk exposure",
    "sensitive_data_map": "Understand where sensitive data lives and how it flows",
    "coverage_gaps": "Identify workloads not yet covered by DLP or labeling policies",
}

EDM_WORKFLOW = [
    {"step": "Define schema", "description": "Specify columns (e.g., SSN, Employee ID, Patient MRN)"},
    {"step": "Hash and upload", "description": "Hash sensitive data table and upload to Purview"},
    {"step": "Create SIT", "description": "Create Exact Data Match sensitive info type referencing schema"},
    {"step": "Use in DLP", "description": "Reference EDM SIT in DLP policies for precise detection"},
    {"step": "Refresh schedule", "description": "Set up periodic refresh as source data changes"},
]


class PurviewDataSecurityAgent(BasicAgent):
    "Demonstrates Microsoft Purview data security: labels, DLP, DSPM, investigations, EDM."

    def __init__(self):
        self.name = "PurviewDataSecurity"
        self.metadata = {
            "name": self.name,
            "description": (
                "Demonstrates Microsoft Purview data security capabilities including "
                "sensitivity labeling, DLP policy creation and simulation, endpoint DLP, "
                "Data Security Posture Management (DSPM), data security investigations, "
                "and Exact Data Match sensitive info types. Can generate scripts, "
                "explain policies, and build demo scenarios for customer engagements."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "explain_labels",
                            "create_label_policy",
                            "create_dlp_policy",
                            "simulate_dlp",
                            "endpoint_dlp",
                            "data_security_investigations",
                            "dspm",
                            "exact_data_match",
                            "demo_scenario",
                            "status",
                        ],
                        "description": (
                            "'explain_labels' — show sensitivity label hierarchy and protection settings; "
                            "'create_label_policy' — generate script to publish labels to users/groups; "
                            "'create_dlp_policy' — generate DLP policy from template or custom rules; "
                            "'simulate_dlp' — simulate a DLP policy to show what would be caught; "
                            "'endpoint_dlp' — extend DLP to Windows/Mac endpoints; "
                            "'data_security_investigations' — investigate data security incidents; "
                            "'dspm' — Data Security Posture Management insights and recommendations; "
                            "'exact_data_match' — create EDM-based sensitive info types from structured data; "
                            "'demo_scenario' — build an end-to-end demo scenario for a customer; "
                            "'status' — summarize current data security posture."
                        ),
                    },
                    "template": {
                        "type": "string",
                        "enum": ["financial", "healthcare", "pii", "custom_fabric"],
                        "description": "DLP policy template to use.",
                    },
                    "scope": {
                        "type": "string",
                        "description": "Target scope — user group, department, or 'org-wide'.",
                    },
                    "customer_industry": {
                        "type": "string",
                        "description": "Customer's industry for tailoring demo scenarios.",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "status")

        if action == "explain_labels":
            return self._explain_labels()
        elif action == "create_dlp_policy":
            return self._create_dlp_policy(kwargs.get("template", "pii"))
        elif action == "data_security_investigations":
            return self._data_security_investigations()
        elif action == "dspm":
            return self._dspm()
        elif action == "exact_data_match":
            return self._exact_data_match()
        elif action == "demo_scenario":
            return self._demo_scenario(kwargs.get("customer_industry", "general"))
        elif action == "status":
            return self._status()
        else:
            return json.dumps({
                "action": action,
                "message": f"Action '{action}' acknowledged. In a live environment, this would call the Microsoft Purview Data Security APIs.",
                "api_endpoint": "https://compliance.microsoft.com",
                "powershell_module": "ExchangeOnlineManagement / SecurityComplianceCenter",
            }, indent=2)

    def _explain_labels(self):
        return json.dumps({
            "title": "Sensitivity Label Hierarchy",
            "description": "Labels protect data at rest, in transit, and in use across M365, Fabric, and Azure.",
            "labels": SENSITIVITY_LABEL_TIERS,
            "key_points": [
                "Labels persist with the document — they travel with the data",
                "Fabric inherits labels from upstream sources (e.g., Excel → Lakehouse)",
                "Labels can auto-apply via trainable classifiers or sensitive info types",
                "Encryption prevents unauthorized access even if file is exfiltrated",
            ],
        }, indent=2)

    def _create_dlp_policy(self, template):
        policy = DLP_POLICY_TEMPLATES.get(template, DLP_POLICY_TEMPLATES["pii"])
        return json.dumps({
            "title": f"DLP Policy: {policy['name']}",
            "policy": policy,
            "powershell_script": (
                f"# Connect to Security & Compliance PowerShell\n"
                f"Connect-IPPSSession\n\n"
                f"# Create DLP policy: {policy['name']}\n"
                f"New-DlpCompliancePolicy -Name '{policy['name']}' "
                f"-ExchangeLocation All -SharePointLocation All -OneDriveLocation All "
                f"-TeamsLocation All -Mode Enable\n\n"
                f"# Add rule with sensitive info types\n"
                f"New-DlpComplianceRule -Name '{policy['name']} - Rule' "
                f"-Policy '{policy['name']}' "
                f"-ContentContainsSensitiveInformation @{{Name='{policy['sensitive_info_types'][0]}'; minCount='1'}} "
                f"-BlockAccess $true -NotifyUser Owner\n"
            ),
            "next_steps": [
                "Test in simulation mode first (New-DlpCompliancePolicy -Mode TestWithNotifications)",
                "Review matched items in Activity Explorer",
                "Gradually expand scope from pilot group to org-wide",
            ],
        }, indent=2)

    def _data_security_investigations(self):
        return json.dumps({
            "title": "Data Security Investigations",
            "description": (
                "End-to-end investigation of data security incidents — correlate signals "
                "from DLP, endpoint activity, audit logs, and insider risk to determine scope and impact."
            ),
            "scenarios": DATA_SECURITY_INVESTIGATIONS_SCENARIOS,
            "investigation_workflow": [
                "1. Alert triage — review DLP or insider risk alert in Purview portal",
                "2. Scope assessment — determine what data was accessed/shared and by whom",
                "3. Evidence collection — correlate audit logs, endpoint signals, sharing events",
                "4. Impact analysis — classify sensitivity of exposed data",
                "5. Remediation — revoke access, apply labels, notify affected parties",
                "6. Post-incident — update policies to prevent recurrence",
            ],
            "key_capabilities": [
                "Unified investigation experience across DLP, IRM, and audit signals",
                "Timeline view of all user data activities",
                "Content inspection for sensitive data identification",
                "Integration with eDiscovery for legal escalation",
            ],
        }, indent=2)

    def _dspm(self):
        return json.dumps({
            "title": "Data Security Posture Management (DSPM)",
            "description": (
                "DSPM provides visibility into your data security posture — where sensitive data "
                "lives, how it's protected, and where gaps exist."
            ),
            "capabilities": DSPM_CAPABILITIES,
            "key_insights": [
                "Sensitive data inventory across M365, Fabric, and Azure",
                "Policy coverage analysis — which workloads lack DLP protection",
                "Oversharing detection — files shared broadly that contain sensitive data",
                "Label adoption metrics — % of sensitive content with appropriate labels",
                "Risk trending — posture improvement or degradation over time",
            ],
            "requirements": [
                "Microsoft 365 E5 or E5 Compliance",
                "Purview Data Security Posture Management license",
                "Data classification scanning enabled",
            ],
        }, indent=2)

    def _exact_data_match(self):
        return json.dumps({
            "title": "Exact Data Match (EDM) Sensitive Info Types",
            "description": (
                "EDM lets you create custom sensitive info types based on exact values from "
                "your structured data (e.g., employee IDs, patient MRNs, custom account numbers). "
                "Unlike regex-based SITs, EDM has near-zero false positives."
            ),
            "workflow": EDM_WORKFLOW,
            "advantages_over_regex": [
                "Near-zero false positives — matches exact values from your database",
                "Handles multi-column correlation (e.g., name + SSN together)",
                "Automatically updates as source data changes (via refresh)",
                "No sensitive data stored in policy — only hashes uploaded",
            ],
            "use_cases": [
                "Healthcare: Match exact patient MRN numbers from EHR system",
                "Financial: Detect specific account numbers from banking systems",
                "HR: Identify employee records by exact ID + name combination",
                "Custom: Any structured data unique to your organization",
            ],
            "powershell_example": (
                "# Create EDM schema\n"
                "New-DlpEdmSchema -FileData (Get-Content .\\edm_schema.xml -Encoding Byte)\n\n"
                "# Hash and upload sensitive data\n"
                "EdmUploadAgent.exe /DataFile:.\\sensitive_data.csv "
                "/HashFile:.\\hash_output.edmhash /Schema:PatientRecords\n"
            ),
        }, indent=2)

    def _demo_scenario(self, industry):
        return json.dumps({
            "title": f"Data Security Demo Scenario — {industry.title()}",
            "scenario_steps": [
                "1. Show sensitivity labels applied to a SharePoint document",
                "2. Attempt to share a labeled 'Highly Confidential' file externally → blocked by DLP",
                "3. Show the DLP incident in the Purview compliance portal",
                "4. Demonstrate auto-labeling: upload a file with credit card numbers → auto-classified",
                "5. Show Fabric integration: label applied to Lakehouse table propagates to Power BI report",
                "6. Show DSPM dashboard: posture insights across workloads and coverage gaps",
                "7. Demo EDM: upload hashed employee data, show precise DLP detection with zero false positives",
            ],
            "demo_data_needed": [
                "Sample documents with synthetic PII (use Microsoft's sample data generators)",
                "Two test users: one normal, one simulating insider risk",
                "A Fabric workspace with labeled Lakehouse data",
            ],
            "talk_track": (
                f"For {industry} customers, emphasize regulatory compliance, "
                f"data residency, and the unified approach across M365 + Fabric + Azure."
            ),
        }, indent=2)

    def _status(self):
        return json.dumps({
            "agent": self.name,
            "capabilities": list(DLP_POLICY_TEMPLATES.keys()),
            "label_tiers": len(SENSITIVITY_LABEL_TIERS),
            "tenant": TARGET_M365_TENANT["tenant_id"],
            "compliance_portal": "https://compliance.microsoft.com",
        }, indent=2)
