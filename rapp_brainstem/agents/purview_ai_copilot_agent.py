"""
Purview AI & Copilot Agent — demonstrates Microsoft Purview's AI and Copilot
governance capabilities: DSPM for AI, Security Copilot for Purview, and
triage agents for DLP and Insider Risk Management.

Scenarios for customer demos:
  1. DSPM for AI — discover and govern AI interactions, sensitive data in prompts
  2. Security Copilot for Purview — natural language investigation and remediation
  3. Triage Agent in DLP — AI-assisted alert triage for data loss prevention
  4. Triage Agent in IRM — AI-assisted alert triage for insider risk management

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES


# ── AI & Copilot governance capabilities ───────────────────────────────────

DSPM_FOR_AI_CAPABILITIES = {
    "discover_ai_apps": {
        "description": "Discover sanctioned and unsanctioned AI applications in use across the org",
        "insights": ["Which AI apps employees use", "Volume of interactions", "Sensitive data shared with AI"],
    },
    "sensitivity_labels_for_ai": {
        "description": "Extend sensitivity labels to AI interactions and outputs",
        "insights": ["Label inheritance in AI-generated content", "Auto-labeling for AI outputs"],
    },
    "dlp_for_ai_prompts": {
        "description": "DLP policies that detect sensitive data in AI prompts before submission",
        "insights": ["Block PII in prompts", "Warn on confidential data", "Audit prompt content"],
    },
    "ai_interaction_audit": {
        "description": "Full audit trail of AI interactions for compliance review",
        "insights": ["Who used which AI app", "What data was shared", "Response content logging"],
    },
    "oversharing_detection": {
        "description": "Detect and remediate overshared content that AI tools could surface",
        "insights": ["Files accessible to Copilot with excessive permissions", "Sensitivity-aware access reviews"],
    },
}

SECURITY_COPILOT_SCENARIOS = {
    "investigate_dlp_alert": {
        "description": "Use natural language to investigate a DLP alert",
        "example_prompt": "Show me all DLP alerts for user John.Smith in the last 7 days and summarize the risk",
        "capabilities": ["Alert correlation", "User activity timeline", "Recommended actions"],
    },
    "summarize_insider_risk": {
        "description": "Summarize insider risk signals for a user under investigation",
        "example_prompt": "Summarize the insider risk profile for the user who triggered alert IRM-2025-0142",
        "capabilities": ["Risk scoring explanation", "Activity pattern analysis", "Peer comparison"],
    },
    "compliance_posture": {
        "description": "Query compliance posture and get improvement recommendations",
        "example_prompt": "What are my top 5 compliance gaps for GDPR and how do I fix them?",
        "capabilities": ["Gap analysis", "Prioritized remediation", "Implementation guidance"],
    },
    "ediscovery_assist": {
        "description": "Natural language assistance for eDiscovery case management",
        "example_prompt": "Find all emails between these two custodians mentioning Project Falcon in Q4 2024",
        "capabilities": ["Query building", "Result summarization", "Review prioritization"],
    },
}

TRIAGE_AGENT_DLP = {
    "description": (
        "AI-powered triage agent that automatically reviews DLP alerts, "
        "determines severity, and recommends or takes action."
    ),
    "workflow": [
        "1. DLP alert generated (e.g., sensitive file shared externally)",
        "2. Triage agent evaluates context: user role, data sensitivity, sharing history",
        "3. Agent classifies: true positive, false positive, or needs human review",
        "4. For true positives: recommends block, revoke access, or notify manager",
        "5. For false positives: auto-dismisses with documented reasoning",
        "6. Escalates ambiguous cases to human analyst with summary",
    ],
    "automation_levels": {
        "monitor_only": "Agent triages and recommends, human approves all actions",
        "semi_automated": "Agent auto-resolves false positives, escalates true positives",
        "fully_automated": "Agent resolves all but highest-severity alerts autonomously",
    },
}

TRIAGE_AGENT_IRM = {
    "description": (
        "AI-powered triage agent that automatically reviews Insider Risk Management alerts, "
        "correlates signals, and prioritizes cases for analyst review."
    ),
    "workflow": [
        "1. IRM alert generated (e.g., elevated exfiltration score)",
        "2. Triage agent correlates with HR signals, DLP events, and access patterns",
        "3. Agent assesses: is this consistent with normal job function?",
        "4. For confirmed risks: creates case with evidence summary",
        "5. For routine activity: documents rationale and dismisses",
        "6. Provides analyst with prioritized case queue and investigation notes",
    ],
    "key_signals_correlated": [
        "HR connector data (resignation, PIP, role changes)",
        "DLP policy matches in same timeframe",
        "Access pattern deviations from peer group",
        "Device enrollment/unenrollment events",
        "Badge access anomalies (if integrated)",
    ],
}


class PurviewAICopilotAgent(BasicAgent):
    """Demonstrates Microsoft Purview AI & Copilot governance: DSPM for AI, Security Copilot, triage agents."""

    def __init__(self):
        self.name = "PurviewAICopilot"
        self.metadata = {
            "name": self.name,
            "description": (
                "Demonstrates Microsoft Purview AI and Copilot governance capabilities: "
                "Data Security Posture Management for AI (discover and govern AI interactions), "
                "Security Copilot for Purview (natural language investigation), "
                "Triage Agent for DLP (automated alert triage), and "
                "Triage Agent for IRM (automated insider risk triage). "
                "Generates governance configurations and demo scenarios."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "dspm_for_ai",
                            "security_copilot",
                            "triage_agent_dlp",
                            "triage_agent_irm",
                            "demo_scenario",
                            "status",
                        ],
                        "description": (
                            "'dspm_for_ai' — discover and govern AI app usage and sensitive data in prompts; "
                            "'security_copilot' — natural language investigation and remediation in Purview; "
                            "'triage_agent_dlp' — AI-powered DLP alert triage and resolution; "
                            "'triage_agent_irm' — AI-powered insider risk alert triage and correlation; "
                            "'demo_scenario' — build end-to-end AI governance demo; "
                            "'status' — current agent capabilities."
                        ),
                    },
                    "scenario": {
                        "type": "string",
                        "enum": list(SECURITY_COPILOT_SCENARIOS.keys()),
                        "description": "Specific Security Copilot scenario to demonstrate.",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "status")

        if action == "dspm_for_ai":
            return self._dspm_for_ai()
        elif action == "security_copilot":
            return self._security_copilot(kwargs.get("scenario", "investigate_dlp_alert"))
        elif action == "triage_agent_dlp":
            return self._triage_agent_dlp()
        elif action == "triage_agent_irm":
            return self._triage_agent_irm()
        elif action == "demo_scenario":
            return self._demo_scenario()
        elif action == "status":
            return self._status()
        else:
            return json.dumps({
                "action": action,
                "message": f"Action '{action}' acknowledged. Would call Purview AI governance APIs.",
                "portal": "https://purview.microsoft.com",
            }, indent=2)

    def _dspm_for_ai(self):
        return json.dumps({
            "title": "Data Security Posture Management for AI",
            "description": (
                "DSPM for AI provides visibility into how AI applications are used across "
                "your organization and helps ensure sensitive data isn't inadvertently "
                "shared with AI services."
            ),
            "capabilities": DSPM_FOR_AI_CAPABILITIES,
            "key_value": [
                "Discover which AI apps employees use (sanctioned and shadow AI)",
                "Detect sensitive data being shared in AI prompts",
                "Apply DLP policies to AI interactions",
                "Monitor for overshared content that Copilot could surface",
                "Extend sensitivity labels to AI-generated content",
            ],
            "deployment_steps": [
                "1. Enable DSPM for AI in the Purview portal",
                "2. Configure AI app discovery (Microsoft and third-party)",
                "3. Create DLP policies targeting AI interactions",
                "4. Set up sensitivity label inheritance for AI outputs",
                "5. Review oversharing reports and remediate permissions",
                "6. Monitor AI interaction audit logs",
            ],
            "supported_ai_apps": [
                "Microsoft Copilot for Microsoft 365",
                "Azure OpenAI Service",
                "ChatGPT (Enterprise and consumer)",
                "Google Gemini",
                "Third-party AI apps via Cloud App Security integration",
            ],
        }, indent=2)

    def _security_copilot(self, scenario):
        sc = SECURITY_COPILOT_SCENARIOS.get(scenario, SECURITY_COPILOT_SCENARIOS["investigate_dlp_alert"])
        return json.dumps({
            "title": f"Security Copilot for Purview — {sc['description']}",
            "description": (
                "Security Copilot brings natural language interaction to Purview, "
                "allowing analysts to investigate, summarize, and take action using "
                "conversational prompts instead of navigating complex UIs."
            ),
            "scenario": sc,
            "all_scenarios": SECURITY_COPILOT_SCENARIOS,
            "integration_points": [
                "Embedded in Purview DLP alert details",
                "Available in Insider Risk Management investigations",
                "Accessible from Compliance Manager improvement actions",
                "Integrated into eDiscovery review sets",
            ],
            "value_proposition": [
                "Reduce investigation time from hours to minutes",
                "Lower the expertise bar for junior analysts",
                "Consistent investigation methodology across team",
                "Natural language summarization for leadership reporting",
            ],
        }, indent=2)

    def _triage_agent_dlp(self):
        return json.dumps({
            "title": "Triage Agent for DLP",
            "agent": TRIAGE_AGENT_DLP,
            "key_benefits": [
                "Reduce analyst workload by 60-80% through automated triage",
                "Faster response time — alerts triaged in seconds vs. hours",
                "Consistent classification criteria eliminates human bias",
                "Documented reasoning for every triage decision (auditable)",
                "Analysts focus on highest-value investigations",
            ],
            "configuration": {
                "sensitivity_threshold": "High — agent handles Medium and Low automatically",
                "false_positive_learning": "Agent improves over time based on analyst overrides",
                "escalation_criteria": [
                    "Executive-level users involved",
                    "Highly confidential data types (M&A, PII at scale)",
                    "Repeated violations by same user within 24 hours",
                ],
            },
        }, indent=2)

    def _triage_agent_irm(self):
        return json.dumps({
            "title": "Triage Agent for Insider Risk Management",
            "agent": TRIAGE_AGENT_IRM,
            "key_benefits": [
                "Correlates signals across multiple data sources automatically",
                "Distinguishes routine activity from genuine risk with context",
                "Prioritizes analyst queue by risk severity and confidence",
                "Reduces false positive fatigue — analysts see pre-filtered alerts",
                "Provides investigation starting points with evidence summaries",
            ],
            "privacy_safeguards": [
                "Agent operates within RBAC boundaries — only accesses permitted data",
                "Pseudonymization preserved until analyst escalates",
                "No direct access to email/file content — metadata and signals only",
                "All agent decisions logged for compliance audit",
            ],
        }, indent=2)

    def _demo_scenario(self):
        return json.dumps({
            "title": "AI & Copilot Governance Demo Scenario",
            "scenario_steps": [
                "1. DSPM for AI — show discovery dashboard of AI apps in use",
                "2. DSPM for AI — demonstrate DLP blocking sensitive data in an AI prompt",
                "3. Security Copilot — investigate a DLP alert using natural language",
                "4. Security Copilot — summarize insider risk profile for a user",
                "5. Triage Agent (DLP) — show automated alert triage resolving false positives",
                "6. Triage Agent (IRM) — show correlated signals creating prioritized case queue",
            ],
            "value_proposition": [
                "AI governance at the speed of AI adoption",
                "Security Copilot reduces investigation time from hours to minutes",
                "Triage agents handle the 80% of routine alerts so analysts can focus",
                "DSPM for AI ensures AI adoption doesn't create compliance gaps",
                "Natural language access democratizes security operations",
            ],
            "licensing": {
                "minimum": "Microsoft 365 E5 (DSPM for AI, triage agents)",
                "recommended": "E5 + Security Copilot (for natural language investigation)",
                "components": [
                    "DSPM for AI — included in M365 E5",
                    "Security Copilot for Purview — Security Copilot license",
                    "Triage Agent for DLP — included in M365 E5 Compliance",
                    "Triage Agent for IRM — included in M365 E5 Insider Risk",
                ],
            },
        }, indent=2)

    def _status(self):
        return json.dumps({
            "agent": self.name,
            "dspm_capabilities": list(DSPM_FOR_AI_CAPABILITIES.keys()),
            "security_copilot_scenarios": list(SECURITY_COPILOT_SCENARIOS.keys()),
            "triage_agents": ["dlp", "irm"],
            "tenant": TARGET_M365_TENANT["tenant_id"],
            "purview_portal": "https://purview.microsoft.com",
        }, indent=2)
