"""
Purview Risk & Compliance Agent — demonstrates Microsoft Purview's risk and
compliance capabilities: insider risk management, communication compliance,
eDiscovery, audit, adaptive protection, information barriers, privileged
access management, and compliance posture scoring.

Scenarios for customer demos:
  1. Insider Risk Management — detect and investigate risky user activities
  2. Communication Compliance — monitor Teams/email for policy violations
  3. eDiscovery (Premium) — legal hold, collection, review, export
  4. Audit (Standard & Premium) — searchable audit log across M365
  5. Compliance Manager — assessment-based compliance posture scoring
  6. Adaptive Protection — dynamic DLP policies based on insider risk signals
  7. Information Barriers — segment users to prevent inappropriate communication
  8. Privileged Access Management — just-in-time access for sensitive tasks

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES


# ── Risk & Compliance capabilities ─────────────────────────────────────────

INSIDER_RISK_INDICATORS = {
    "data_exfiltration": [
        "Mass file download",
        "Printing large volumes of sensitive files",
        "Sharing files to personal email/cloud storage",
        "USB copy of classified documents",
    ],
    "data_leaks": [
        "Sharing via unauthorized channels",
        "DLP policy matches above threshold",
        "Uploading to unsanctioned cloud services",
    ],
    "security_policy_violations": [
        "Visiting phishing/malware sites",
        "Disabling security tools",
        "Using unauthorized VPN or anonymizers",
    ],
    "departing_employee": [
        "File hoarding in final 30 days",
        "Access pattern changes near resignation date",
        "Bulk download of project IP",
    ],
}

COMPLIANCE_FRAMEWORKS = {
    "gdpr": {
        "name": "GDPR (EU General Data Protection Regulation)",
        "assessments": 67,
        "key_controls": ["Data subject rights", "Breach notification", "DPO designation", "Lawful basis"],
    },
    "hipaa": {
        "name": "HIPAA / HITECH",
        "assessments": 45,
        "key_controls": ["PHI safeguards", "Access controls", "Audit logging", "Breach notification"],
    },
    "sox": {
        "name": "SOX (Sarbanes-Oxley)",
        "assessments": 38,
        "key_controls": ["Financial reporting integrity", "Internal controls", "Audit trail", "Access management"],
    },
    "nist_800_53": {
        "name": "NIST 800-53 Rev 5",
        "assessments": 325,
        "key_controls": ["Access control", "Incident response", "Risk assessment", "System protection"],
    },
    "iso_27001": {
        "name": "ISO 27001:2022",
        "assessments": 93,
        "key_controls": ["Information security policy", "Asset management", "Cryptography", "Operations security"],
    },
    "pci_dss": {
        "name": "PCI DSS v4.0",
        "assessments": 64,
        "key_controls": ["Network security", "Cardholder data protection", "Access control", "Monitoring"],
    },
}

EDISCOVERY_WORKFLOW = [
    {"phase": "Identification", "description": "Identify custodians and data sources relevant to the case"},
    {"phase": "Preservation", "description": "Place legal holds on custodian mailboxes, OneDrive, Teams"},
    {"phase": "Collection", "description": "Collect responsive data using search queries and date ranges"},
    {"phase": "Processing", "description": "De-duplicate, extract text/metadata, apply near-duplicate detection"},
    {"phase": "Review", "description": "Review documents with AI-powered relevance scoring and tagging"},
    {"phase": "Analysis", "description": "Themes, email threading, conversation reconstruction"},
    {"phase": "Production", "description": "Export in standard formats (PST, PDF, native) for legal counsel"},
]

ADAPTIVE_PROTECTION_RISK_LEVELS = {
    "elevated": {
        "description": "User shows persistent high-risk signals over multiple sessions",
        "policy_action": "Block sharing externally, enforce mandatory labeling",
        "dlp_override": "No override allowed",
    },
    "moderate": {
        "description": "User triggered multiple low-severity alerts or one high-severity",
        "policy_action": "Warn and require justification for external sharing",
        "dlp_override": "Override with justification",
    },
    "minor": {
        "description": "User shows early or isolated risk signals",
        "policy_action": "Policy tip only, no block",
        "dlp_override": "Standard DLP policies apply",
    },
}

INFORMATION_BARRIERS_SEGMENTS = {
    "investment_banking": {
        "description": "Users in M&A, IPO advisory, or deal teams",
        "blocked_segments": ["research_analysts", "retail_trading"],
        "use_case": "Chinese wall compliance in financial services",
    },
    "research_analysts": {
        "description": "Equity research, market analysis personnel",
        "blocked_segments": ["investment_banking", "proprietary_trading"],
        "use_case": "Prevent material non-public information sharing",
    },
    "hr_leadership": {
        "description": "HR executives and compensation committee",
        "blocked_segments": ["general_population"],
        "use_case": "Protect sensitive employee data and compensation info",
    },
}

PRIVILEGED_ACCESS_SCENARIOS = {
    "exchange_admin": {
        "task": "New-TransportRule / Set-Mailbox",
        "approval_required": True,
        "max_duration_hours": 4,
        "approvers": ["Global Admin", "Compliance Admin"],
    },
    "ediscovery_export": {
        "task": "Export eDiscovery results",
        "approval_required": True,
        "max_duration_hours": 8,
        "approvers": ["Legal Counsel", "Compliance Admin"],
    },
    "role_assignment": {
        "task": "Add-RoleGroupMember for sensitive role groups",
        "approval_required": True,
        "max_duration_hours": 2,
        "approvers": ["Global Admin"],
    },
}


class PurviewRiskComplianceAgent(BasicAgent):
    """Demonstrates Microsoft Purview risk & compliance: insider risk, adaptive protection, eDiscovery, audit, compliance score, information barriers, PAM."""

    def __init__(self):
        self.name = "PurviewRiskCompliance"
        self.metadata = {
            "name": self.name,
            "description": (
                "Demonstrates Microsoft Purview risk and compliance capabilities: "
                "insider risk management, communication compliance, eDiscovery (Premium), "
                "audit log search, Compliance Manager posture scoring, adaptive protection "
                "(dynamic DLP based on risk signals), information barriers, and "
                "privileged access management. Generates policies and demo scenarios."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "insider_risk",
                            "communication_compliance",
                            "ediscovery",
                            "audit_search",
                            "compliance_score",
                            "adaptive_protection",
                            "information_barriers",
                            "privileged_access_management",
                            "demo_scenario",
                            "status",
                        ],
                        "description": (
                            "'insider_risk' — explain/configure insider risk indicators and policies; "
                            "'communication_compliance' — monitor communications for policy violations; "
                            "'ediscovery' — walk through the eDiscovery Premium workflow; "
                            "'audit_search' — search the unified audit log; "
                            "'compliance_score' — show Compliance Manager assessment and score; "
                            "'adaptive_protection' — dynamic DLP based on insider risk levels; "
                            "'information_barriers' — segment users to prevent inappropriate communication; "
                            "'privileged_access_management' — just-in-time access for sensitive tasks; "
                            "'demo_scenario' — build end-to-end compliance demo; "
                            "'status' — current agent capabilities."
                        ),
                    },
                    "framework": {
                        "type": "string",
                        "enum": list(COMPLIANCE_FRAMEWORKS.keys()),
                        "description": "Compliance framework for posture assessment.",
                    },
                    "risk_category": {
                        "type": "string",
                        "enum": list(INSIDER_RISK_INDICATORS.keys()),
                        "description": "Category of insider risk indicators to focus on.",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "status")

        if action == "insider_risk":
            return self._insider_risk(kwargs.get("risk_category", "data_exfiltration"))
        elif action == "ediscovery":
            return self._ediscovery()
        elif action == "compliance_score":
            return self._compliance_score(kwargs.get("framework", "nist_800_53"))
        elif action == "adaptive_protection":
            return self._adaptive_protection()
        elif action == "information_barriers":
            return self._information_barriers()
        elif action == "privileged_access_management":
            return self._privileged_access_management()
        elif action == "audit_search":
            return self._audit_search()
        elif action == "demo_scenario":
            return self._demo_scenario()
        elif action == "status":
            return self._status()
        else:
            return json.dumps({
                "action": action,
                "message": f"Action '{action}' acknowledged. Would call Purview Compliance APIs.",
                "portal": "https://compliance.microsoft.com",
            }, indent=2)

    def _insider_risk(self, category):
        indicators = INSIDER_RISK_INDICATORS.get(category, INSIDER_RISK_INDICATORS["data_exfiltration"])
        return json.dumps({
            "title": f"Insider Risk Management — {category.replace('_', ' ').title()}",
            "category": category,
            "indicators": indicators,
            "policy_template": {
                "name": f"IRM - {category.replace('_', ' ').title()}",
                "triggering_event": (
                    "HR connector signal (resignation)" if category == "departing_employee"
                    else "Cumulative exfiltration score > threshold"
                ),
                "investigation_workflow": [
                    "1. Alert generated when indicator threshold exceeded",
                    "2. Analyst reviews activity timeline in Insider Risk portal",
                    "3. Escalate to case if confirmed risky behavior",
                    "4. Case investigation with full activity context",
                    "5. Remediate: notify manager, restrict access, or escalate to legal",
                ],
            },
            "privacy_controls": [
                "Pseudonymized usernames by default (Analyst sees 'User-1234')",
                "De-anonymization requires dual approval",
                "Activity captured only for in-scope policies",
                "RBAC separates alert triage from investigation from admin",
            ],
        }, indent=2)

    def _ediscovery(self):
        return json.dumps({
            "title": "eDiscovery (Premium) Workflow",
            "description": (
                "End-to-end legal discovery workflow — from identifying custodians "
                "to producing documents for legal review."
            ),
            "workflow": EDISCOVERY_WORKFLOW,
            "key_capabilities": [
                "Custodian management with legal hold notifications",
                "Advanced indexing — handles 300+ file types",
                "Conversation reconstruction — Teams + email threading",
                "Predictive coding / relevance scoring (AI-assisted review)",
                "Near-duplicate detection reduces review volume 30-50%",
                "Privilege detection flags attorney-client communications",
            ],
            "powershell_example": (
                "# Create an eDiscovery case\n"
                "Connect-IPPSSession\n"
                "New-ComplianceCase -Name 'Project Falcon Investigation' "
                "-Description 'Data exfiltration investigation Q1 2025'\n\n"
                "# Create a hold\n"
                "New-CaseHoldPolicy -Case 'Project Falcon Investigation' "
                "-Name 'Custodian Hold' -ExchangeLocation 'user@contoso.com'\n"
            ),
        }, indent=2)

    def _compliance_score(self, framework):
        fw = COMPLIANCE_FRAMEWORKS.get(framework, COMPLIANCE_FRAMEWORKS["nist_800_53"])
        return json.dumps({
            "title": f"Compliance Manager — {fw['name']}",
            "framework": fw,
            "scoring_model": {
                "total_points": fw["assessments"] * 10,
                "categories": [
                    "Microsoft-managed controls (auto-scored)",
                    "Customer-managed controls (manual evidence + testing)",
                    "Shared controls (joint responsibility)",
                ],
                "improvement_actions": [
                    "Enable MFA for all users (+27 points)",
                    "Configure DLP policies for sensitive data (+18 points)",
                    "Enable audit logging across all workloads (+15 points)",
                    "Implement least-privilege access reviews (+22 points)",
                ],
            },
            "multi_cloud": (
                "Compliance Manager now supports assessments for AWS and GCP, "
                "providing a unified compliance view across multi-cloud."
            ),
        }, indent=2)

    def _adaptive_protection(self):
        return json.dumps({
            "title": "Adaptive Protection — Dynamic DLP Based on Insider Risk",
            "description": (
                "Adaptive Protection integrates Insider Risk Management signals with DLP policies. "
                "Users are automatically assigned risk levels, and DLP policies dynamically adjust "
                "based on their current risk score."
            ),
            "risk_levels": ADAPTIVE_PROTECTION_RISK_LEVELS,
            "how_it_works": [
                "1. Insider Risk Management continuously scores user behavior",
                "2. Users are assigned to risk levels (elevated, moderate, minor)",
                "3. DLP policies reference these risk levels as conditions",
                "4. As user risk changes, DLP enforcement automatically adjusts",
                "5. When risk decreases, restrictions are automatically relaxed",
            ],
            "key_benefits": [
                "Reduces alert fatigue — only high-risk users get strict enforcement",
                "Dynamic — automatically adapts as user behavior changes",
                "Privacy-preserving — DLP admins don't see IRM investigation details",
                "No manual intervention needed — fully automated policy adjustment",
            ],
            "prerequisites": [
                "Microsoft 365 E5 or E5 Insider Risk Management add-on",
                "Insider Risk Management policies configured and active",
                "DLP policies created with Adaptive Protection conditions",
            ],
        }, indent=2)

    def _information_barriers(self):
        return json.dumps({
            "title": "Information Barriers — Segment-Based Communication Controls",
            "description": (
                "Information Barriers restrict communication and collaboration between "
                "defined user segments to comply with regulatory requirements (e.g., Chinese walls)."
            ),
            "segments": INFORMATION_BARRIERS_SEGMENTS,
            "enforcement_points": [
                "Microsoft Teams — block chat, calls, and meeting invites between segments",
                "SharePoint Online — prevent site sharing across barrier boundaries",
                "OneDrive for Business — block file sharing between segments",
                "Outlook — block email communication (when configured)",
            ],
            "powershell_example": (
                "# Define segments\n"
                "New-OrganizationSegment -Name 'InvestmentBanking' "
                "-UserGroupFilter \"Department -eq 'Investment Banking'\"\n\n"
                "# Create barrier policy\n"
                "New-InformationBarrierPolicy -Name 'IB-Research' "
                "-AssignedSegment 'ResearchAnalysts' "
                "-SegmentsBlocked 'InvestmentBanking','ProprietaryTrading' "
                "-State Active\n\n"
                "# Apply policies\n"
                "Start-InformationBarrierPoliciesApplication\n"
            ),
            "industries": [
                "Financial services — Chinese walls between deal teams and research",
                "Legal — conflict-of-interest separation between case teams",
                "Education — student safety boundaries",
                "Government — classified information compartmentalization",
            ],
        }, indent=2)

    def _privileged_access_management(self):
        return json.dumps({
            "title": "Privileged Access Management (PAM)",
            "description": (
                "Privileged Access Management enforces just-in-time access for sensitive "
                "admin tasks, requiring approval before elevated permissions are granted."
            ),
            "scenarios": PRIVILEGED_ACCESS_SCENARIOS,
            "workflow": [
                "1. Admin attempts a privileged operation (e.g., New-TransportRule)",
                "2. Request is generated and routed to designated approvers",
                "3. Approver reviews justification and approves/denies",
                "4. If approved, time-limited access is granted",
                "5. Access automatically expires after the configured duration",
                "6. All actions during the elevated session are fully audited",
            ],
            "key_benefits": [
                "Zero standing access — no permanent privileged permissions",
                "Just-in-time — access only when needed, auto-expires",
                "Approval workflow — dual-control for sensitive operations",
                "Full audit trail — who requested, who approved, what was done",
                "Granular — task-level control, not role-level",
            ],
            "powershell_example": (
                "# Enable PAM\n"
                "Enable-ElevatedAccessControl\n\n"
                "# Create access policy\n"
                "New-ElevatedAccessApprovalPolicy -Task 'New-TransportRule' "
                "-ApprovalType 'Manual' -ApproverGroup 'ComplianceAdmins' "
                "-MaxElevationDuration '04:00:00'\n\n"
                "# Submit access request\n"
                "New-ElevatedAccessRequest -Task 'New-TransportRule' "
                "-Reason 'Creating mail flow rule for external tagging'\n"
            ),
        }, indent=2)

    def _audit_search(self):
        return json.dumps({
            "title": "Unified Audit Log Search",
            "description": "Search across 500+ activity types in Microsoft 365.",
            "retention": {
                "standard": "180 days (E3)",
                "premium": "365 days (E5), extendable to 10 years",
            },
            "example_searches": [
                {"query": "FileAccessed by departing users in last 30 days", "use_case": "Insider risk triage"},
                {"query": "MailItemsAccessed by external apps", "use_case": "Compromised account investigation"},
                {"query": "SensitivityLabelApplied events", "use_case": "Label adoption tracking"},
                {"query": "SharePoint sharing events to external domains", "use_case": "Data leak detection"},
            ],
            "powershell": (
                "# Search audit log for file access events\n"
                "Search-UnifiedAuditLog -StartDate (Get-Date).AddDays(-7) "
                "-EndDate (Get-Date) -RecordType SharePointFileOperation "
                "-Operations FileAccessed -ResultSize 5000\n"
            ),
        }, indent=2)

    def _demo_scenario(self):
        return json.dumps({
            "title": "Risk & Compliance Demo Scenario",
            "scenario_steps": [
                "1. Compliance Manager — show posture score and improvement actions",
                "2. Insider Risk — show an alert for a simulated departing employee",
                "3. Adaptive Protection — show dynamic DLP enforcing stricter rules for elevated-risk user",
                "4. Communication Compliance — show a Teams message flagged for inappropriate content",
                "5. eDiscovery — walk through case creation and legal hold placement",
                "6. Audit — search for specific admin activities in the last 24 hours",
                "7. Information Barriers — demonstrate blocked communication between segments",
                "8. Privileged Access — show approval workflow for a sensitive admin operation",
            ],
            "value_proposition": [
                "Single pane of glass for compliance across M365 + multi-cloud",
                "AI-assisted review reduces eDiscovery costs 40-60%",
                "Insider risk detection catches threats before data leaves the org",
                "Adaptive Protection eliminates one-size-fits-all DLP enforcement",
                "Compliance score provides measurable progress for board reporting",
            ],
            "licensing": {
                "minimum": "Microsoft 365 E3 (audit standard, basic compliance)",
                "recommended": "Microsoft 365 E5 or E5 Compliance add-on",
                "premium_features": [
                    "Insider Risk Management",
                    "eDiscovery Premium",
                    "10-year audit retention",
                    "Communication Compliance",
                    "Adaptive Protection",
                    "Information Barriers",
                    "Privileged Access Management",
                ],
            },
        }, indent=2)

    def _status(self):
        return json.dumps({
            "agent": self.name,
            "risk_categories": list(INSIDER_RISK_INDICATORS.keys()),
            "compliance_frameworks": list(COMPLIANCE_FRAMEWORKS.keys()),
            "adaptive_protection_levels": list(ADAPTIVE_PROTECTION_RISK_LEVELS.keys()),
            "information_barrier_segments": list(INFORMATION_BARRIERS_SEGMENTS.keys()),
            "pam_scenarios": list(PRIVILEGED_ACCESS_SCENARIOS.keys()),
            "ediscovery_phases": len(EDISCOVERY_WORKFLOW),
            "tenant": TARGET_M365_TENANT["tenant_id"],
            "compliance_portal": "https://compliance.microsoft.com",
        }, indent=2)
