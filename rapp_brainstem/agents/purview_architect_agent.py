"""
Purview Architect Agent — designs the governance layer for a demo:
classifications, sensitivity labels, DLP policies, glossary, collection
hierarchy, scan scope.

Always reuses the EXISTING Microsoft Purview account (never creates a new
one — that constraint is owned by the Azure Architect / Enterprise Architect).
This agent only designs and hands off to `purview_data_governance` /
`purview_data_security` / `purview_risk_compliance` builder agents.
"""

from agents.basic_agent import BasicAgent


# Industry → sensitivity profile guidance
INDUSTRY_PROFILES = {
    "Healthcare": ["PHI (HIPAA)", "PII", "Patient consent"],
    "Financial Services": ["PCI-DSS", "PII", "MNPI", "AML/KYC"],
    "Government": ["CUI", "PII", "FedRAMP markings"],
    "Defense & Intelligence": ["CUI", "ITAR/EAR", "Classified markings (out of scope for demo)"],
    "Retail & Consumer Goods": ["PII (customer)", "PCI (payment)"],
    "Education": ["FERPA (student records)", "PII"],
    "Energy & Resources": ["SCADA telemetry sensitivity", "PII (workforce)"],
    "Industrials & Manufacturing": ["IP / trade secrets", "Worker safety data"],
    "Telecommunications & Media": ["CPNI", "PII (subscriber)"],
    "Travel Transportation & Hospitality": ["PII (traveler)", "PCI"],
    "Automotive Mobility & Transportation": ["PII (driver)", "Telematics"],
    "Professional Services": ["Client confidentiality", "PII"],
    "Sustainability": ["ESG disclosures", "Supplier data"],
}


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/purview-architect",
    "version": "1.0.0",
    "display_name": "Purview Architect Agent",
    "description": (
        "Designs governance: classifications, sensitivity labels, DLP, glossary, "
        "collection layout, scan scope. Reuses the existing Purview account."
    ),
    "tags": ["architect", "purview", "governance", "compliance", "design"],
    "category": "architecture",
}


class PurviewArchitectAgent(BasicAgent):
    """Governance architect. Reuses the existing Purview account."""

    def __init__(self):
        self.name = "purview_architect"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["design"],
                    },
                    "demo": {"type": "object", "description": "Demo request payload."},
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        if kwargs.get("action") != "design":
            return f"Unknown action: {kwargs.get('action')}"
        return self._design(kwargs.get("demo") or {})

    def _design(self, demo: dict) -> str:
        customer = demo.get("customer_name") or "Customer"
        ind = demo.get("industry_primary") or ""
        ind2 = demo.get("industry_secondary") or ""
        reqs = demo.get("requirements") or []
        techs = demo.get("technologies") or []

        profile = INDUSTRY_PROFILES.get(ind, ["PII", "Confidential"]) + (
            INDUSTRY_PROFILES.get(ind2, []) if ind2 else []
        )
        # de-dupe preserving order
        seen = set()
        profile = [p for p in profile if not (p in seen or seen.add(p))]

        wants_governance = any("govern" in r.lower() or "compliance" in r.lower() or "audit" in r.lower() for r in reqs) \
            or "Microsoft Purview" in techs
        wants_rbac = any("rbac" in r.lower() or "role-based" in r.lower() for r in reqs)

        lines = [
            f"# Purview Architecture — {customer}",
            "",
            f"**Industry profile:** {ind}" + (f" / {ind2}" if ind2 else ""),
            f"**Purview account:** *(reuse existing — do not create new)*",
            "",
            "## Sensitivity Profile (industry-driven)",
        ]
        for p in profile:
            lines.append(f"- {p}")
        lines += [
            "",
            "## Collection Hierarchy",
            "```",
            f"Root",
            f"└── Demos",
            f"    └── {customer}",
            f"        ├── Bronze (raw)",
            f"        ├── Silver (conformed)",
            f"        └── Gold (analytics-ready)",
            "```",
            "",
            "## Classifications to Apply",
            "- Built-in: PII, Credit Card, Email Address, IP Address (US, EU)",
            "- Industry-specific (custom): " + (", ".join(profile) if profile else "—"),
            "",
            "## Sensitivity Labels",
            "- `Public` — synthetic / sample data only",
            "- `General` — gold layer summaries",
            "- `Confidential — Demo` — anything that mirrors real customer-like data",
            "",
            "## DLP & Policies",
        ]
        if wants_governance:
            lines += [
                "- Enable Purview Information Protection scan over the demo workspace.",
                "- Sensitivity label inheritance: Lakehouse → tables → downstream Semantic Model.",
                "- Audit: enable Purview Audit, retain 30 days for the demo.",
            ]
        else:
            lines.append("- Governance not requested; minimal DLP — auto-label only obvious PII for the talk track.")
        lines.append("")

        if wants_rbac:
            lines += [
                "## RBAC",
                "- Data Steward: Dave",
                "- Data Curator: demo team",
                "- Data Reader: viewers (customers attending the demo)",
                "",
            ]

        lines += [
            "## Glossary Seeds",
            "Suggest 3–5 industry terms for the glossary (e.g. for Retail: `SKU`, `Basket`, `Shrinkage`).",
            "",
            "## Hand-off (builder agents)",
            "- `purview_data_governance` — register the workspace, run classification scan, apply labels.",
            "- `purview_data_security` — apply DLP and sensitivity-label rules.",
            "- `purview_risk_compliance` — wire compliance score and audit retention if requested.",
        ]
        return "\n".join(lines)
