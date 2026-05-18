"""
Demo Orchestrator Agent — takes a customer scenario description, decomposes it
into end-to-end steps, delegates to the appropriate specialist agents, tracks
progress, and produces a complete runbook.

This is the "meta-agent" that ties the entire demo platform together:
  - Understands what a full data platform demo requires
  - Knows the capabilities of every specialist agent
  - Creates a sequenced execution plan
  - Generates a runbook document for delivery

Example scenario:
  "Contoso Retail wants to see real-time inventory analytics with natural
   language querying in Teams and data governance via Purview."

The orchestrator would plan:
  1. DataEngineer → provision workspace, Lakehouse, ingest data
  2. FabricMirroring → mirror POS database into OneLake
  3. RealTimeIntelligence → Eventstream for inventory updates
  4. SemanticModel → star schema, DAX measures
  5. DataAnalyst → register in Purview, classify PII
  6. FabricDataAgentBuilder → create Data Agent on gold layer
  7. CopilotStudioConnector → wire to Teams copilot
  8. FoundryAgentBuilder → (optional) code-first agent

Drop this file into any brainstem agents/ directory.
"""

import json
from agents.basic_agent import BasicAgent


# ── Registry of all specialist agents ──────────────────────────────────────

AGENT_REGISTRY = {
    "data_engineer": {
        "display": "Data Engineer Agent",
        "file": "data_engineer_agent.py",
        "capabilities": [
            "Provision Fabric workspace & Lakehouse",
            "Create Azure resources (Event Hubs, Storage, SQL)",
            "Generate ingestion pipelines (batch & streaming)",
            "CAF-compliant naming & tagging",
        ],
        "when_to_use": "Setting up infrastructure, provisioning workspaces, data ingestion",
    },
    "data_analyst": {
        "display": "Data Analyst (Governance) Agent",
        "file": "data_analyst_agent.py",
        "capabilities": [
            "Register assets in Microsoft Purview",
            "Run classification scans",
            "Create glossary terms & assign owners",
            "Track lineage across pipelines",
        ],
        "when_to_use": "Data governance, cataloging, PII classification, compliance",
    },
    "fabric_mirroring": {
        "display": "Fabric Mirroring Agent",
        "file": "fabric_mirroring_agent.py",
        "capabilities": [
            "Zero-ETL replication from Azure SQL, Cosmos DB, Snowflake, Postgres, MySQL",
            "Continuous delta sync to OneLake",
            "Monitor replication health",
        ],
        "when_to_use": "Replacing ETL with continuous mirroring, near-real-time data in Lakehouse",
    },
    "realtime_intelligence": {
        "display": "Real-Time Intelligence Agent",
        "file": "fabric_realtime_intelligence_agent.py",
        "capabilities": [
            "Create Eventstreams from Event Hubs, IoT Hub, Kafka, CDC",
            "Create KQL Databases & Eventhouses",
            "Real-Time Dashboards with auto-refresh",
            "Activator alerts (threshold-based triggers)",
        ],
        "when_to_use": "Streaming analytics, real-time dashboards, event-driven alerts",
    },
    "semantic_model": {
        "display": "Semantic Model Agent",
        "file": "semantic_model_agent.py",
        "capabilities": [
            "Create Direct Lake semantic models",
            "Generate DAX measures (YTD, MoM, Running Total)",
            "Build star schema relationships",
            "Generate Power BI report layouts",
        ],
        "when_to_use": "BI layer, Power BI reports, semantic modeling, DAX measures",
    },
    "fabric_data_agent_builder": {
        "display": "Fabric Data Agent Builder",
        "file": "fabric_data_agent_builder.py",
        "capabilities": [
            "Create Fabric Data Agents (NL → SQL)",
            "Configure grounding tables",
            "Add business context instructions",
            "Generate API endpoints for integration",
        ],
        "when_to_use": "Natural language data access, AI-powered querying, API endpoint for copilots",
    },
    "copilot_studio_connector": {
        "display": "Copilot Studio Connector Agent",
        "file": "copilot_studio_connector_agent.py",
        "capabilities": [
            "Create Copilot Studio copilots",
            "Connect to Fabric Data Agents (plugin)",
            "Configure SSO/OAuth authentication",
            "Deploy to Teams, Web, M365 Copilot channels",
            "Create declarative agent manifests",
        ],
        "when_to_use": "User-facing copilots, Teams bots, M365 Copilot integration",
    },
    "foundry_agent_builder": {
        "display": "Foundry Agent Builder",
        "file": "foundry_agent_builder_agent.py",
        "capabilities": [
            "Scaffold Microsoft Agent Framework projects",
            "Add Fabric Data Agent as a tool",
            "Configure tracing (OpenTelemetry → App Insights)",
            "Set up batch & continuous evaluation",
            "Deploy to Foundry (hosted or container)",
        ],
        "when_to_use": "Code-first agents, complex orchestration, production deployment with eval",
    },
    "m365_template_factory": {
        "display": "M365 Template Factory Agent",
        "file": "m365_template_factory_agent.py",
        "capabilities": [
            "Generate complete M365 agent delivery bundles",
            "Teams app manifests, adaptive cards",
            "Power Platform solution packaging",
        ],
        "when_to_use": "Packaging solutions for customer delivery, Teams app bundles",
    },
}

# ── Demo scenario templates ────────────────────────────────────────────────

SCENARIO_TEMPLATES = {
    "retail_analytics": {
        "title": "Retail Analytics with Real-Time Inventory",
        "description": "POS data → OneLake → real-time inventory dashboard → Teams copilot",
        "steps": [
            ("data_engineer", "Provision workspace, Lakehouse, ingest POS data (batch)"),
            ("fabric_mirroring", "Mirror SQL POS database for continuous sync"),
            ("realtime_intelligence", "Eventstream from Event Hubs for live inventory updates"),
            ("semantic_model", "Star schema: fact_sales, dim_product, dim_store, dim_date"),
            ("data_analyst", "Register in Purview, classify customer PII"),
            ("fabric_data_agent_builder", "Data Agent on gold layer for NL queries"),
            ("copilot_studio_connector", "Teams copilot for store managers"),
        ],
    },
    "healthcare_compliance": {
        "title": "Healthcare Data Platform with Governance",
        "description": "EHR data → governed Lakehouse → compliant AI querying",
        "steps": [
            ("data_engineer", "Provision workspace with sensitivity labels"),
            ("fabric_mirroring", "Mirror Cosmos DB patient records"),
            ("data_analyst", "Purview scan for PHI/PII, apply sensitivity labels"),
            ("semantic_model", "Aggregated models (no patient-level data in BI)"),
            ("fabric_data_agent_builder", "Data Agent with RLS for role-based access"),
            ("foundry_agent_builder", "Custom agent with audit logging for compliance"),
        ],
    },
    "manufacturing_iot": {
        "title": "Manufacturing IoT with Predictive Alerts",
        "description": "Sensor data → Eventstream → KQL → Activator alerts → Teams notifications",
        "steps": [
            ("data_engineer", "Provision workspace, create Event Hub for sensors"),
            ("realtime_intelligence", "Eventstream from IoT Hub, KQL Database, Real-Time Dashboard"),
            ("realtime_intelligence", "Activator alert: temperature > threshold → Teams notification"),
            ("semantic_model", "Historical analytics model for trend analysis"),
            ("fabric_data_agent_builder", "Data Agent for maintenance team queries"),
            ("copilot_studio_connector", "Teams bot for factory floor managers"),
        ],
    },
    "financial_services": {
        "title": "Financial Services Reporting with M365 Copilot",
        "description": "Transaction data → governed Lakehouse → M365 Copilot for analysts",
        "steps": [
            ("data_engineer", "Provision workspace, ingest transaction feeds"),
            ("fabric_mirroring", "Mirror Azure SQL trade database"),
            ("data_analyst", "Purview governance, glossary for financial terms"),
            ("semantic_model", "Direct Lake model with financial DAX measures"),
            ("fabric_data_agent_builder", "Data Agent for financial queries"),
            ("copilot_studio_connector", "Declarative agent for M365 Copilot"),
            ("m365_template_factory", "Package as Teams app for analyst distribution"),
        ],
    },
    "full_platform": {
        "title": "Complete Data Platform Demo (All Technologies)",
        "description": "Shows batch + streaming + mirroring + AI + governance end-to-end",
        "steps": [
            ("data_engineer", "Provision full workspace: Lakehouse, Warehouse, pipelines"),
            ("fabric_mirroring", "Mirror external databases (Azure SQL + Cosmos DB)"),
            ("realtime_intelligence", "Eventstream + KQL + Real-Time Dashboard + Activator"),
            ("semantic_model", "Direct Lake model + DAX + Power BI report"),
            ("data_analyst", "Full Purview governance: scan, classify, glossary, lineage"),
            ("fabric_data_agent_builder", "Data Agent on gold layer"),
            ("copilot_studio_connector", "Teams copilot + M365 Copilot declarative agent"),
            ("foundry_agent_builder", "Code-first Foundry agent with eval pipeline"),
            ("m365_template_factory", "Packaged delivery bundle for customer"),
        ],
    },
}


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/demo-orchestrator",
    "version": "1.0.0",
    "display_name": "Demo Orchestrator Agent",
    "description": (
        "Takes a customer scenario, decomposes it into sequenced steps, delegates "
        "to specialist agents (DataEngineer, Mirroring, RealTime, SemanticModel, "
        "Purview, DataAgent, CopilotStudio, Foundry), and produces a complete "
        "demo runbook. The meta-agent that orchestrates the entire platform."
    ),
    "author": "Kody",
    "tags": ["orchestrator", "demo", "planning", "runbook", "end-to-end"],
    "category": "orchestration",
    "quality_tier": "community",
    "dependencies": ["@rapp/basic_agent"],
}


class DemoOrchestratorAgent(BasicAgent):
    """Orchestrates end-to-end demo scenarios by delegating to specialist agents."""

    def __init__(self):
        self.name = "demo_orchestrator"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "plan_demo", "list_templates", "list_agents",
                            "generate_runbook", "estimate_effort",
                            "recommend_scenario", "best_practices",
                        ],
                        "description": "Action to perform",
                    },
                    "scenario": {
                        "type": "string",
                        "description": "Customer scenario description (free text)",
                    },
                    "template": {
                        "type": "string",
                        "enum": list(SCENARIO_TEMPLATES.keys()),
                        "description": "Pre-built scenario template to use",
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer/company name for the demo",
                    },
                    "requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific requirements (batch, streaming, governance, etc.)",
                    },
                    "technologies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Technologies to include (Fabric, Purview, Copilot Studio, Foundry, etc.)",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "list_templates")
        scenario = kwargs.get("scenario", "")
        template = kwargs.get("template", "")
        customer_name = kwargs.get("customer_name", "Customer")
        requirements = kwargs.get("requirements", [])
        technologies = kwargs.get("technologies", [])

        handlers = {
            "list_templates": lambda: self._list_templates(),
            "list_agents": lambda: self._list_agents(),
            "plan_demo": lambda: self._plan_demo(scenario, template, customer_name, requirements, technologies),
            "generate_runbook": lambda: self._generate_runbook(scenario, template, customer_name, requirements, technologies),
            "estimate_effort": lambda: self._estimate_effort(template, requirements),
            "recommend_scenario": lambda: self._recommend_scenario(requirements, technologies),
            "best_practices": lambda: self._best_practices(),
        }

        handler = handlers.get(action)
        if handler:
            return handler()
        return f"Unknown action: {action}"

    # ── Handlers ───────────────────────────────────────────────────────────

    def _list_templates(self):
        lines = ["# Demo Scenario Templates\n"]
        for key, tmpl in SCENARIO_TEMPLATES.items():
            lines.append(f"## {tmpl['title']} (`{key}`)\n")
            lines.append(f"{tmpl['description']}\n")
            lines.append("**Steps:**")
            for i, (agent, desc) in enumerate(tmpl["steps"], 1):
                agent_info = AGENT_REGISTRY.get(agent, {})
                lines.append(f"  {i}. [{agent_info.get('display', agent)}] {desc}")
            lines.append("")
        return "\n".join(lines)

    def _list_agents(self):
        lines = ["# Available Specialist Agents\n"]
        for key, agent in AGENT_REGISTRY.items():
            lines.append(f"## {agent['display']} (`{key}`)\n")
            lines.append(f"**File:** `agents/{agent['file']}`\n")
            lines.append(f"**Use when:** {agent['when_to_use']}\n")
            lines.append("**Capabilities:**")
            for cap in agent["capabilities"]:
                lines.append(f"  - {cap}")
            lines.append("")
        return "\n".join(lines)

    def _plan_demo(self, scenario, template, customer_name, requirements, technologies):
        # If a template is specified, use it
        if template and template in SCENARIO_TEMPLATES:
            tmpl = SCENARIO_TEMPLATES[template]
            steps = tmpl["steps"]
            title = tmpl["title"]
            description = tmpl["description"]
        else:
            # Auto-plan based on requirements and scenario
            steps = self._auto_plan(scenario, requirements, technologies)
            title = f"Custom Demo for {customer_name}"
            description = scenario or "Custom scenario based on requirements"

        lines = [
            f"# Demo Plan: {title}\n",
            f"**Customer:** {customer_name}\n",
            f"**Description:** {description}\n\n",
        ]

        if requirements:
            lines.append("**Requirements:**")
            for r in requirements:
                lines.append(f"- {r}")
            lines.append("")

        if technologies:
            lines.append("**Technologies:**")
            for t in technologies:
                lines.append(f"- {t}")
            lines.append("")

        lines.append("---\n")
        lines.append("## Execution Plan\n")
        lines.append("| # | Agent | Task | Depends On |")
        lines.append("|---|-------|------|------------|")

        for i, (agent, desc) in enumerate(steps, 1):
            agent_info = AGENT_REGISTRY.get(agent, {})
            depends = "—" if i == 1 else f"Step {i-1}"
            # Some steps have parallel dependencies
            if agent in ("data_analyst", "semantic_model") and i > 2:
                depends = "Steps 1-2"
            lines.append(f"| {i} | {agent_info.get('display', agent)} | {desc} | {depends} |")

        lines.append("\n## Architecture Diagram\n")
        lines.append("```")
        lines.append(self._generate_architecture(steps))
        lines.append("```\n")

        lines.append("## Agent Invocations\n")
        lines.append("To execute this plan, call each agent in sequence:\n")
        for i, (agent, desc) in enumerate(steps, 1):
            lines.append(f"**Step {i}:** `@kody/{agent.replace('_', '-')}` → {desc}\n")

        return "\n".join(lines)

    def _generate_runbook(self, scenario, template, customer_name, requirements, technologies):
        plan = self._plan_demo(scenario, template, customer_name, requirements, technologies)

        # Add runbook-specific sections
        if template and template in SCENARIO_TEMPLATES:
            tmpl = SCENARIO_TEMPLATES[template]
            steps = tmpl["steps"]
        else:
            steps = self._auto_plan(scenario, requirements, technologies)

        runbook = [
            plan,
            "\n---\n",
            "# RUNBOOK: Detailed Execution Guide\n",
            f"**Customer:** {customer_name}\n",
            f"**Prepared by:** Innovation Hub (davidwin@onemtc.net)\n",
            f"**Tenant:** MCAPS ({TARGET_M365_TENANT['tenant_id']})\n\n",
            "## Prerequisites\n",
            "- [ ] Azure CLI authenticated to EXP tenant\n",
            "- [ ] Fabric capacity available (F64 or trial)\n",
            "- [ ] Copilot Studio license (if using Copilot path)\n",
            "- [ ] M365 Copilot license (if using M365 Copilot path)\n",
            "- [ ] Sample data prepared\n\n",
            "## Pre-Demo Checklist\n",
            "- [ ] All services provisioned and healthy\n",
            "- [ ] Sample data loaded and queryable\n",
            "- [ ] Data Agent tested with sample questions\n",
            "- [ ] Copilot/Agent tested end-to-end\n",
            "- [ ] Screen sharing configured\n",
            "- [ ] Backup plan if live demo fails\n\n",
        ]

        # Detailed steps
        runbook.append("## Detailed Steps\n")
        for i, (agent, desc) in enumerate(steps, 1):
            agent_info = AGENT_REGISTRY.get(agent, {})
            runbook.append(f"### Step {i}: {desc}\n")
            runbook.append(f"**Agent:** `{agent_info.get('display', agent)}`\n")
            runbook.append(f"**File:** `agents/{agent_info.get('file', 'unknown')}`\n\n")
            runbook.append("**Actions:**")
            for cap in agent_info.get("capabilities", [])[:3]:
                runbook.append(f"- {cap}")
            runbook.append("")
            runbook.append(f"**Validation:** ✅ Verify {desc.lower()} is working before proceeding\n")
            runbook.append("---\n")

        # Demo script
        runbook.append("## Demo Script (Talking Points)\n")
        runbook.append("1. **Open:** Show the business problem / customer scenario\n")
        runbook.append("2. **Architecture:** Walk through the data flow diagram\n")
        runbook.append("3. **Data:** Show data landing in Lakehouse (batch + streaming)\n")
        runbook.append("4. **Governance:** Show Purview catalog, classifications\n")
        runbook.append("5. **BI:** Show Power BI report with Direct Lake model\n")
        runbook.append("6. **AI:** Ask a question in natural language → watch SQL generation\n")
        runbook.append("7. **Copilot:** Show the Teams/M365 copilot experience\n")
        runbook.append("8. **Close:** Recap how all pieces connect\n")

        return "\n".join(runbook)

    def _estimate_effort(self, template, requirements):
        if template and template in SCENARIO_TEMPLATES:
            steps = SCENARIO_TEMPLATES[template]["steps"]
        else:
            steps = self._auto_plan("", requirements, [])

        # Effort estimates per agent type (in hours)
        effort_map = {
            "data_engineer": 2.0,
            "data_analyst": 1.5,
            "fabric_mirroring": 1.0,
            "realtime_intelligence": 2.5,
            "semantic_model": 1.5,
            "fabric_data_agent_builder": 1.0,
            "copilot_studio_connector": 2.0,
            "foundry_agent_builder": 3.0,
            "m365_template_factory": 1.5,
        }

        lines = ["# Effort Estimate\n"]
        lines.append("| Step | Agent | Estimated Hours |")
        lines.append("|------|-------|-----------------|")

        total = 0.0
        for i, (agent, desc) in enumerate(steps, 1):
            hours = effort_map.get(agent, 1.5)
            total += hours
            agent_info = AGENT_REGISTRY.get(agent, {})
            lines.append(f"| {i} | {agent_info.get('display', agent)} | {hours:.1f}h |")

        lines.append(f"| | **TOTAL** | **{total:.1f}h** |")
        lines.append("")
        lines.append(f"**Note:** These are estimates for building the demo from scratch.")
        lines.append(f"Subsequent demos reusing the same workspace are much faster (~30 min setup).")

        return "\n".join(lines)

    def _recommend_scenario(self, requirements, technologies):
        """Recommend a scenario template based on requirements."""
        scores = {}

        for key, tmpl in SCENARIO_TEMPLATES.items():
            score = 0
            agents_used = [agent for agent, _ in tmpl["steps"]]

            # Score based on technology match
            tech_map = {
                "fabric": ["data_engineer", "fabric_mirroring", "realtime_intelligence", "semantic_model"],
                "purview": ["data_analyst"],
                "copilot studio": ["copilot_studio_connector"],
                "foundry": ["foundry_agent_builder"],
                "m365": ["copilot_studio_connector", "m365_template_factory"],
                "streaming": ["realtime_intelligence"],
                "mirroring": ["fabric_mirroring"],
                "batch": ["data_engineer"],
                "governance": ["data_analyst"],
                "ai": ["fabric_data_agent_builder", "foundry_agent_builder"],
            }

            for tech in technologies:
                for mapped_agent in tech_map.get(tech.lower(), []):
                    if mapped_agent in agents_used:
                        score += 2

            for req in requirements:
                req_lower = req.lower()
                if "real-time" in req_lower or "streaming" in req_lower:
                    if "realtime_intelligence" in agents_used:
                        score += 3
                if "governance" in req_lower or "purview" in req_lower:
                    if "data_analyst" in agents_used:
                        score += 3
                if "copilot" in req_lower or "teams" in req_lower:
                    if "copilot_studio_connector" in agents_used:
                        score += 3
                if "mirror" in req_lower:
                    if "fabric_mirroring" in agents_used:
                        score += 3

            scores[key] = score

        # Sort by score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        lines = ["# Recommended Scenarios\n"]
        lines.append("Based on your requirements and technologies:\n")

        for i, (key, score) in enumerate(ranked[:3], 1):
            tmpl = SCENARIO_TEMPLATES[key]
            medal = ["🥇", "🥈", "🥉"][i-1]
            lines.append(f"## {medal} {tmpl['title']} (`{key}`) — Score: {score}\n")
            lines.append(f"{tmpl['description']}\n")
            lines.append(f"Steps: {len(tmpl['steps'])} | Agents: {len(set(a for a, _ in tmpl['steps']))}\n")

        if not requirements and not technologies:
            lines.append("\n**Tip:** Provide requirements or technologies for better recommendations.")
            lines.append("Example: `requirements=['streaming', 'governance']`, `technologies=['Fabric', 'Purview', 'Copilot Studio']`")

        return "\n".join(lines)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _auto_plan(self, scenario, requirements, technologies):
        """Auto-generate a plan based on free-text scenario and requirements."""
        steps = []

        # Always start with data engineering
        steps.append(("data_engineer", "Provision workspace, Lakehouse, and data ingestion"))

        # Add based on requirements/technologies
        req_lower = " ".join(requirements).lower() + " " + " ".join(technologies).lower() + " " + scenario.lower()

        if "mirror" in req_lower or "replicate" in req_lower or "zero-etl" in req_lower:
            steps.append(("fabric_mirroring", "Mirror external databases to OneLake"))

        if "stream" in req_lower or "real-time" in req_lower or "iot" in req_lower or "event" in req_lower:
            steps.append(("realtime_intelligence", "Streaming pipeline: Eventstream → KQL → Dashboard"))

        # Semantic model for BI
        if "bi" in req_lower or "report" in req_lower or "power bi" in req_lower or "dashboard" in req_lower or not requirements:
            steps.append(("semantic_model", "Direct Lake semantic model with DAX measures"))

        # Governance
        if "purview" in req_lower or "govern" in req_lower or "classif" in req_lower or "compliance" in req_lower:
            steps.append(("data_analyst", "Register in Purview, scan, classify, create glossary"))

        # AI / Data Agent
        if "ai" in req_lower or "natural language" in req_lower or "data agent" in req_lower or "copilot" in req_lower or not requirements:
            steps.append(("fabric_data_agent_builder", "Create Data Agent for natural language queries"))

        # Copilot Studio
        if "copilot studio" in req_lower or "teams" in req_lower or "m365" in req_lower or "bot" in req_lower:
            steps.append(("copilot_studio_connector", "Create copilot and deploy to Teams/M365"))

        # Foundry
        if "foundry" in req_lower or "agent framework" in req_lower or "code" in req_lower:
            steps.append(("foundry_agent_builder", "Scaffold Foundry agent with Data Agent tool"))

        # M365 packaging
        if "m365" in req_lower or "package" in req_lower or "deliver" in req_lower:
            steps.append(("m365_template_factory", "Package as M365 delivery bundle"))

        # If no specific requirements, include a sensible default set
        if len(steps) <= 1:
            steps = [
                ("data_engineer", "Provision workspace, Lakehouse, ingest sample data"),
                ("semantic_model", "Create Direct Lake model with measures"),
                ("fabric_data_agent_builder", "Create Data Agent for NL queries"),
                ("copilot_studio_connector", "Wire to Teams copilot"),
            ]

        return steps

    def _generate_architecture(self, steps):
        """Generate a simple ASCII architecture diagram."""
        agents_used = set(agent for agent, _ in steps)

        lines = []
        lines.append("┌─────────────────────────────────────────────────────┐")
        lines.append("│                 DATA SOURCES                         │")
        lines.append("│  [Azure SQL] [Cosmos DB] [Event Hubs] [Files]       │")
        lines.append("└───────────────────────┬─────────────────────────────┘")
        lines.append("                        │")
        lines.append("                        ▼")

        if "fabric_mirroring" in agents_used or "realtime_intelligence" in agents_used:
            lines.append("┌─────────────────────────────────────────────────────┐")
            if "fabric_mirroring" in agents_used:
                lines.append("│  [Mirroring]     ──▶  OneLake (continuous sync)     │")
            if "realtime_intelligence" in agents_used:
                lines.append("│  [Eventstream]   ──▶  KQL Database (streaming)      │")
            lines.append("│  [Pipeline]      ──▶  Lakehouse (batch)             │")
            lines.append("└───────────────────────┬─────────────────────────────┘")
        else:
            lines.append("┌─────────────────────────────────────────────────────┐")
            lines.append("│  [Pipeline]      ──▶  Lakehouse (batch)             │")
            lines.append("└───────────────────────┬─────────────────────────────┘")

        lines.append("                        │")
        lines.append("                        ▼")
        lines.append("┌─────────────────────────────────────────────────────┐")
        lines.append("│              ANALYTICS & AI LAYER                    │")

        if "semantic_model" in agents_used:
            lines.append("│  [Semantic Model] → Power BI (Direct Lake)          │")
        if "fabric_data_agent_builder" in agents_used:
            lines.append("│  [Data Agent]     → Natural Language → SQL          │")
        if "data_analyst" in agents_used:
            lines.append("│  [Purview]        → Governance, Classification       │")
        lines.append("└───────────────────────┬─────────────────────────────┘")
        lines.append("                        │")
        lines.append("                        ▼")
        lines.append("┌─────────────────────────────────────────────────────┐")
        lines.append("│              CONSUMPTION LAYER                       │")

        if "copilot_studio_connector" in agents_used:
            lines.append("│  [Copilot Studio] → Teams / M365 Copilot            │")
        if "foundry_agent_builder" in agents_used:
            lines.append("│  [Foundry Agent]  → Custom AI Agent (code-first)    │")
        if "m365_template_factory" in agents_used:
            lines.append("│  [M365 Package]   → Customer delivery bundle        │")
        lines.append("└─────────────────────────────────────────────────────┘")

        return "\n".join(lines)

    def _best_practices(self):
        lines = ["# Cross-Cutting Best Practices (All Services)\n"]
        lines.append("*Each specialist agent has its own `best_practices` action with detailed guidance.*\n")
        lines.append("## Universal Principles\n")
        lines.append("- **Identity:** Microsoft Entra ID everywhere — Managed Identity for services, user tokens for data access")
        lines.append("- **Secrets:** Azure Key Vault — never hardcode credentials in code, configs, or prompts")
        lines.append("- **Governance:** Microsoft Purview for cataloging, classification, lineage, DLP")
        lines.append("- **Security:** Least privilege RBAC, Row-Level Security, sensitivity labels")
        lines.append("- **Naming:** Consistent conventions (e.g., `lh-<domain>-<env>`, `es-<source>-<purpose>`)")
        lines.append("- **Environments:** Dev → Test → Prod with deployment pipelines")
        lines.append("- **Monitoring:** Set up alerts and dashboards from day one")
        lines.append("")
        lines.append("## Per-Service Best Practices (invoke each agent with action='best_practices')\n")
        lines.append("| Agent | Key Focus |")
        lines.append("|-------|-----------|")
        lines.append("| `fabric_mirroring` | PKs required, max 500-1000 tables, Managed Identity auth |")
        lines.append("| `realtime_intelligence` | Hot/cold paths, retention policies, KQL optimization |")
        lines.append("| `semantic_model` | Row groups 1-16M, no calc columns on DL, star schema |")
        lines.append("| `fabric_data_agent_builder` | Descriptive names, one agent per audience, read-only |")
        lines.append("| `copilot_studio_connector` | Entra ID SSO, DLP policies, gated releases |")
        lines.append("| `foundry_agent_builder` | Lifecycle (create→trace→eval→publish), redact PII |")
        lines.append("")
        lines.append("## Demo Planning Checklist\n")
        lines.append("- [ ] Workspace provisioned with appropriate capacity")
        lines.append("- [ ] Authentication configured (EXP tenant, Entra ID)")
        lines.append("- [ ] Data sources identified and accessible")
        lines.append("- [ ] Governance policies defined (Purview)")
        lines.append("- [ ] Security model designed (RBAC, RLS)")
        lines.append("- [ ] Each service configured per best practices")
        lines.append("- [ ] End-to-end tested before customer demo")
        return "\n".join(lines)
