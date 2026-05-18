"""
Fabric Data Agent Builder — creates Microsoft Fabric Data Agents that expose
Lakehouse/Warehouse data via natural language (AI-powered SQL generation).

Fabric Data Agents are the bridge between data and AI:
  - They sit on top of Lakehouse SQL endpoints or Warehouses
  - Users ask questions in natural language → Agent generates SQL → returns results
  - Can be consumed by Copilot Studio, M365 Agents, Foundry agents, or direct API

This agent:
  1. Creates Fabric Data Agents
  2. Configures grounding tables (what data the agent can access)
  3. Adds instructions/context for better answers
  4. Tests with sample questions
  5. Generates connection details for Copilot Studio / Foundry integration

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES, get_fabric_auth_preamble


# ── Fabric Data Agent configuration ───────────────────────────────────────

DATA_AGENT_CAPABILITIES = {
    "natural_language_query": "Users ask questions in plain English → SQL generated automatically",
    "schema_awareness": "Agent understands table schemas, relationships, column descriptions",
    "context_grounding": "Custom instructions help agent understand business context",
    "multi_table_join": "Handles queries across multiple tables with proper JOINs",
    "aggregation": "Supports GROUP BY, HAVING, window functions via natural language",
    "security": "Respects RLS (Row-Level Security) and workspace permissions",
}

# ── Recommended grounding patterns ────────────────────────────────────────

GROUNDING_PATTERNS = {
    "star_schema": {
        "description": "Fact + Dimension tables (classic data warehouse)",
        "tables": ["fact_*", "dim_*"],
        "instructions": "This is a star schema. Fact tables contain measures (amounts, counts). Dimension tables contain attributes (names, categories, dates).",
    },
    "medallion": {
        "description": "Bronze/Silver/Gold layers (Lakehouse pattern)",
        "tables": ["gold_*"],
        "instructions": "Query the gold layer tables. These are clean, business-ready aggregates. Avoid bronze (raw) or silver (cleaned) tables.",
    },
    "domain_specific": {
        "description": "Domain-aligned tables (e.g. sales, inventory, customers)",
        "tables": ["sales_*", "customers_*", "products_*"],
        "instructions": "Tables are organized by business domain. Use appropriate domain tables for each question.",
    },
}

# ── Microsoft Best Practices for Fabric Data Agents ────────────────────────

BEST_PRACTICES = {
    "data_preparation": [
        "Use descriptive column names — 'ActiveCustomer' not 'ActCu' or 'C1'",
        "Add column descriptions in Lakehouse/Warehouse metadata (aids AI SQL generation)",
        "Ensure primary keys and foreign keys are defined for proper JOIN inference",
        "Remove or exclude internal/system columns that shouldn't be queried",
        "Maintain consistent naming conventions across all exposed tables",
    ],
    "agent_design": [
        "Create ONE agent per audience/use-case (Sales team, Finance team, etc.)",
        "Limit exposed tables to what's relevant — fewer tables = better accuracy",
        "Provide AI instructions with business context, terminology, and default filters",
        "Include example queries that demonstrate expected question patterns",
        "Configure verified answers for critical/common questions (deterministic responses)",
        "Document the agent's scope and limitations for end users",
    ],
    "security_and_governance": [
        "Data Agent enforces read-only access — no INSERT/UPDATE/DELETE possible",
        "Uses requesting user's Entra ID credentials (not a service account)",
        "Respects Row-Level Security (RLS) on the underlying data source",
        "Integrates with Microsoft Purview DLP and access restriction policies",
        "Govern publishing with approval steps — don't auto-publish to production",
        "Apply sensitivity labels that flow through to responses",
        "Least privilege: only grant workspace access to intended consumers",
    ],
    "quality_and_testing": [
        "Test generated SQL for accuracy before publishing",
        "Review DAX/SQL in responses — AI can generate syntactically correct but semantically wrong queries",
        "Validate edge cases: NULLs, empty results, ambiguous questions",
        "Iterate on instructions based on failed test queries",
        "Monitor query patterns post-launch to improve instructions",
    ],
    "supported_data_sources": [
        "Lakehouse (via SQL Analytics Endpoint)",
        "Warehouse",
        "Power BI Semantic Model (Direct Lake or Import)",
        "KQL Database (for real-time data)",
        "Ontology (knowledge graph, if configured)",
    ],
}


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/fabric-data-agent-builder",
    "version": "1.0.0",
    "display_name": "Fabric Data Agent Builder",
    "description": (
        "Create Microsoft Fabric Data Agents that let users query Lakehouse/Warehouse "
        "data in natural language. Configure grounding tables, add business context, "
        "test queries, and generate integration endpoints for Copilot Studio and Foundry."
    ),
    "author": "Kody",
    "tags": ["fabric", "data-agent", "ai", "natural-language", "sql", "copilot"],
    "category": "ai",
    "quality_tier": "community",
    "dependencies": ["@rapp/basic_agent"],
}


class FabricDataAgentBuilder(BasicAgent):
    """Creates and configures Fabric Data Agents for natural language data access."""

    def __init__(self):
        self.name = "fabric_data_agent_builder"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "create", "configure_tables", "add_instructions",
                            "test_query", "get_endpoint", "list_capabilities",
                            "full_setup", "best_practices",
                        ],
                        "description": "Action to perform",
                    },
                    "workspace": {
                        "type": "string",
                        "description": "Fabric workspace name",
                    },
                    "agent_name": {
                        "type": "string",
                        "description": "Name for the Data Agent",
                    },
                    "lakehouse_or_warehouse": {
                        "type": "string",
                        "description": "Name of the Lakehouse or Warehouse to ground the agent on",
                    },
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tables to expose to the Data Agent",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Business context/instructions for the agent (helps it understand your data)",
                    },
                    "sample_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Sample questions to test the agent with",
                    },
                    "grounding_pattern": {
                        "type": "string",
                        "enum": list(GROUNDING_PATTERNS.keys()),
                        "description": "Pre-built grounding pattern to apply",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "list_capabilities")
        workspace = kwargs.get("workspace", "demo-workspace")
        agent_name = kwargs.get("agent_name", "data-agent-demo")
        lakehouse = kwargs.get("lakehouse_or_warehouse", "lakehouse-gold")
        tables = kwargs.get("tables", [])
        instructions = kwargs.get("instructions", "")
        sample_questions = kwargs.get("sample_questions", [])
        grounding_pattern = kwargs.get("grounding_pattern", "star_schema")

        handlers = {
            "list_capabilities": lambda: self._list_capabilities(),
            "create": lambda: self._create_agent(workspace, agent_name, lakehouse),
            "configure_tables": lambda: self._configure_tables(workspace, agent_name, lakehouse, tables, grounding_pattern),
            "add_instructions": lambda: self._add_instructions(workspace, agent_name, instructions, grounding_pattern),
            "test_query": lambda: self._test_query(workspace, agent_name, sample_questions),
            "get_endpoint": lambda: self._get_endpoint(workspace, agent_name),
            "full_setup": lambda: self._full_setup(
                workspace, agent_name, lakehouse, tables, instructions, sample_questions, grounding_pattern
            ),
            "best_practices": lambda: self._best_practices(),
        }

        handler = handlers.get(action)
        if handler:
            return handler()
        return f"Unknown action: {action}"

    # ── Handlers ───────────────────────────────────────────────────────────

    def _list_capabilities(self):
        lines = ["# Fabric Data Agent Capabilities\n"]
        lines.append("A Fabric Data Agent lets anyone query your data in plain English.\n")
        for key, desc in DATA_AGENT_CAPABILITIES.items():
            lines.append(f"- **{key.replace('_', ' ').title()}**: {desc}")
        lines.append("\n## How It Works\n")
        lines.append("```")
        lines.append("User: \"What were total sales last quarter by region?\"")
        lines.append("       │")
        lines.append("       ▼")
        lines.append("[Fabric Data Agent]")
        lines.append("  1. Understands schema (tables, columns, types)")
        lines.append("  2. Reads your custom instructions (business context)")
        lines.append("  3. Generates SQL query")
        lines.append("  4. Executes against Lakehouse/Warehouse SQL endpoint")
        lines.append("  5. Returns formatted results")
        lines.append("       │")
        lines.append("       ▼")
        lines.append("Answer: Table/chart with sales by region for Q4")
        lines.append("```\n")
        lines.append("## Consumption Paths\n")
        lines.append("| Consumer | How |")
        lines.append("|----------|-----|")
        lines.append("| Copilot Studio | Add as a Knowledge source or Plugin |")
        lines.append("| M365 Copilot | Via Copilot Studio declarative agent |")
        lines.append("| Foundry Agent | Call as a tool via REST API |")
        lines.append("| Power BI | Copilot in Power BI uses Data Agents |")
        lines.append("| Direct API | REST endpoint for custom apps |")
        return "\n".join(lines)

    def _create_agent(self, workspace, agent_name, lakehouse):
        auth = get_fabric_auth_preamble(workspace)
        script = (
            f'"""\n'
            f'Create Fabric Data Agent: {agent_name}\n'
            f'Grounded on: {lakehouse}\n'
            f'Workspace: {workspace}\n'
            f'"""\n\n'
            f'{auth}\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# Step 1: Create the Data Agent item\n'
            f'payload = {{\n'
            f'    "displayName": "{agent_name}",\n'
            f'    "type": "DataAgent",\n'
            f'    "description": "AI-powered data agent for natural language queries over {lakehouse}"\n'
            f'}}\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/items",\n'
            f'    headers=headers,\n'
            f'    json=payload\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'agent = resp.json()\n'
            f'agent_id = agent["id"]\n'
            f'print(f"Data Agent created: {{agent_id}}")\n\n'
            f'# Step 2: Connect to Lakehouse/Warehouse SQL endpoint\n'
            f'# This is configured in the Fabric portal Data Agent editor:\n'
            f'# 1. Open the Data Agent → Settings\n'
            f'# 2. Select data source: "{lakehouse}"\n'
            f'# 3. Choose tables to expose\n'
            f'# 4. Add instructions for business context\n\n'
            f'print(f"Configure in portal:")\n'
            f'print(f"  https://app.fabric.microsoft.com/groups/{{workspace_id}}/dataagents/{{agent_id}}")\n'
        )

        return (
            f"## Create Fabric Data Agent: `{agent_name}`\n\n"
            f"**Data Source:** {lakehouse}\n"
            f"**Workspace:** {workspace}\n\n"
            f"```python\n{script}\n```\n"
        )

    def _configure_tables(self, workspace, agent_name, lakehouse, tables, grounding_pattern):
        pattern = GROUNDING_PATTERNS.get(grounding_pattern, GROUNDING_PATTERNS["star_schema"])

        if not tables:
            tables = pattern.get("tables", ["fact_sales", "dim_customer", "dim_product", "dim_date"])

        lines = [
            f"## Configure Data Agent Tables: `{agent_name}`\n",
            f"**Pattern:** {pattern['description']}\n",
            f"**Tables to expose:**\n",
        ]
        for t in tables:
            lines.append(f"- `{t}`")

        lines.append(f"\n### Grounding Configuration\n")
        lines.append("In the Data Agent editor, select these tables and add column descriptions:\n")
        lines.append("| Table | Purpose | Key Columns |")
        lines.append("|-------|---------|-------------|")
        for t in tables:
            if "fact" in t.lower():
                lines.append(f"| {t} | Measures/transactions | amount, quantity, date_key |")
            elif "dim" in t.lower():
                dim_type = t.replace("dim_", "").title()
                lines.append(f"| {t} | {dim_type} attributes | {t.replace('dim_', '')}_id, name, category |")
            else:
                lines.append(f"| {t} | Business data | (add descriptions in portal) |")

        lines.append(f"\n### Best Practices\n")
        lines.append("1. **Add column descriptions** — helps the AI understand what each column means")
        lines.append("2. **Mark key columns** — relationships help with JOINs")
        lines.append("3. **Use business-friendly names** — `Total Revenue` beats `sum_amt_usd`")
        lines.append("4. **Limit exposed tables** — only include what users should query")
        lines.append(f"5. **Apply RLS** — Row-Level Security carries through to agent responses")

        return "\n".join(lines)

    def _add_instructions(self, workspace, agent_name, instructions, grounding_pattern):
        pattern = GROUNDING_PATTERNS.get(grounding_pattern, GROUNDING_PATTERNS["star_schema"])

        if not instructions:
            instructions = pattern.get("instructions", "")

        example_instructions = (
            f"You are a data analyst assistant for the {workspace} workspace.\n\n"
            f"{instructions}\n\n"
            f"Guidelines:\n"
            f"- Always use the gold/fact tables for aggregations\n"
            f"- Join dimension tables for descriptive attributes\n"
            f"- Default date range: last 12 months unless specified\n"
            f"- Currency is USD unless stated otherwise\n"
            f"- When asked about 'revenue', use the Amount column in fact_sales\n"
            f"- Customer segments: Enterprise, SMB, Consumer\n"
            f"- Regions: North America, EMEA, APAC, LATAM\n"
        )

        return (
            f"## Instructions for Data Agent: `{agent_name}`\n\n"
            f"Add these instructions in the Data Agent editor → Instructions tab:\n\n"
            f"```\n{example_instructions}\n```\n\n"
            f"### Why Instructions Matter\n"
            f"- Without instructions, the agent only knows column names and types\n"
            f"- Instructions provide **business context**: what terms mean, default filters, domain rules\n"
            f"- Better instructions = more accurate SQL generation\n\n"
            f"### Instruction Tips\n"
            f"- Define business terms (\"revenue\" = `SUM(fact_sales.Amount)`)\n"
            f"- Specify default filters (last 12 months)\n"
            f"- Explain relationships between tables\n"
            f"- Note any data quirks (NULL handling, excluded statuses)\n"
        )

    def _test_query(self, workspace, agent_name, sample_questions):
        if not sample_questions:
            sample_questions = [
                "What were total sales last quarter?",
                "Show me top 10 customers by revenue",
                "What's the month-over-month growth trend?",
                "Which product category has the highest margin?",
                "How many new customers did we acquire this year?",
            ]

        auth = get_fabric_auth_preamble(workspace)
        script = (
            f'{auth}\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n'
            f'agent_id = "<data-agent-id>"\n\n'
            f'# Test the Data Agent with sample questions\n'
            f'questions = {json.dumps(sample_questions, indent=4)}\n\n'
            f'for q in questions:\n'
            f'    print(f"\\nQ: {{q}}")\n'
            f'    resp = requests.post(\n'
            f'        f"{{FABRIC_API}}/workspaces/{{workspace_id}}/dataAgents/{{agent_id}}/query",\n'
            f'        headers=headers,\n'
            f'        json={{"question": q}}\n'
            f'    )\n'
            f'    if resp.status_code == 200:\n'
            f'        result = resp.json()\n'
            f'        print(f"SQL: {{result.get(\'generatedSql\', \'N/A\')}}")\n'
            f'        print(f"Answer: {{result.get(\'answer\', \'N/A\')}}")\n'
            f'    else:\n'
            f'        print(f"Error: {{resp.status_code}} — {{resp.text}}")\n'
            f'    print("---")\n'
        )

        return (
            f"## Test Data Agent: `{agent_name}`\n\n"
            f"### Sample Questions\n"
            + "\n".join(f"- {q}" for q in sample_questions)
            + f"\n\n```python\n{script}\n```\n\n"
            f"### Evaluation Criteria\n"
            f"- Does the generated SQL correctly answer the question?\n"
            f"- Are JOINs appropriate and efficient?\n"
            f"- Does it respect the instructions (default date range, terminology)?\n"
            f"- Are results formatted clearly?\n"
        )

    def _get_endpoint(self, workspace, agent_name):
        return (
            f"## Data Agent Endpoint: `{agent_name}`\n\n"
            f"### REST API (Direct)\n"
            f"```\n"
            f"POST https://api.fabric.microsoft.com/v1/workspaces/<workspace-id>/dataAgents/<agent-id>/query\n"
            f"Authorization: Bearer <token>  (scope: {SCOPES['fabric']})\n"
            f"Content-Type: application/json\n\n"
            f'{{"question": "What were total sales last month?"}}\n'
            f"```\n\n"
            f"### Authentication\n"
            f"- **Target Tenant:** `{TARGET_M365_TENANT['tenant_id']}`\n"
            f"- **Identity:** `{TARGET_M365_TENANT['login_hint']}`\n"
            f"- **Scope:** `{SCOPES['fabric']}`\n\n"
            f"### Integration Paths\n\n"
            f"| Platform | Integration Method |\n"
            f"|----------|-------------------|\n"
            f"| **Copilot Studio** | Add as Plugin → HTTP action pointing to Data Agent API |\n"
            f"| **M365 Copilot** | Via Copilot Studio declarative agent with Data Agent plugin |\n"
            f"| **Foundry Agent** | Register as a tool in your Agent Framework code |\n"
            f"| **Power Automate** | HTTP connector calling the Data Agent endpoint |\n"
            f"| **Custom App** | Direct REST API call with Entra ID token |\n"
            f"| **Teams Bot** | Bot Framework → calls Data Agent API |\n\n"
            f"### Copilot Studio Plugin Manifest\n"
            f"```yaml\n"
            f"name: {agent_name}\n"
            f"description: Query data in natural language\n"
            f"auth:\n"
            f"  type: OAuthImplicit\n"
            f"  authority: {TARGET_M365_TENANT['authority']}\n"
            f"  clientId: <app-registration-client-id>\n"
            f"  scopes: {SCOPES['fabric']}\n"
            f"functions:\n"
            f"  - name: queryData\n"
            f"    description: Ask a question about the data\n"
            f"    parameters:\n"
            f"      - name: question\n"
            f"        type: string\n"
            f"        description: Natural language question\n"
            f"    returns: Answer with data\n"
            f"```\n"
        )

    def _full_setup(self, workspace, agent_name, lakehouse, tables, instructions, sample_questions, grounding_pattern):
        sections = [
            f"# Full Fabric Data Agent Setup: `{agent_name}`\n",
            f"**Workspace:** {workspace}\n",
            f"**Data Source:** {lakehouse}\n\n---\n",
            self._create_agent(workspace, agent_name, lakehouse),
            "\n---\n",
            self._configure_tables(workspace, agent_name, lakehouse, tables, grounding_pattern),
            "\n---\n",
            self._add_instructions(workspace, agent_name, instructions, grounding_pattern),
            "\n---\n",
            self._test_query(workspace, agent_name, sample_questions),
            "\n---\n",
            self._get_endpoint(workspace, agent_name),
            "\n---\n",
            "## Next Steps\n\n"
            "1. **Copilot Studio** → Use `copilot_studio_connector` agent to wire this Data Agent to a copilot\n"
            "2. **Foundry** → Use `foundry_agent_builder` agent to create a code-first agent that calls this Data Agent\n"
            "3. **Power BI** → Copilot in Power BI automatically uses Data Agents in the workspace\n",
        ]
        return "\n".join(sections)

    def _best_practices(self):
        lines = ["# Fabric Data Agent — Best Practices\n"]
        lines.append("*Source: Microsoft Learn documentation (2025)*\n")
        for category, practices in BEST_PRACTICES.items():
            lines.append(f"\n## {category.replace('_', ' ').title()}\n")
            for p in practices:
                lines.append(f"- {p}")
        lines.append("\n\n## Key Security Model\n")
        lines.append("```")
        lines.append("[User] → [Entra ID Auth] → [Fabric Data Agent]")
        lines.append("                                    │")
        lines.append("                                    ├─ Uses USER's identity (not service account)")
        lines.append("                                    ├─ Enforces RLS on data source")
        lines.append("                                    ├─ Read-only (no writes possible)")
        lines.append("                                    └─ Purview DLP policies apply")
        lines.append("```")
        lines.append(f"\n📖 Docs: https://learn.microsoft.com/fabric/data-science/concept-data-agent")
        return "\n".join(lines)
