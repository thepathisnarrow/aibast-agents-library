"""
Foundry Agent Builder — scaffolds Microsoft Agent Framework code that uses
Fabric Data Agents (and other tools) as callable tools. Sets up tracing,
evaluation, and deployment to Microsoft Foundry.

Architecture:
  [Foundry Agent (Python)]
     ├── Tool: Fabric Data Agent (NL → SQL queries)
     ├── Tool: Web Search (Bing grounding)
     ├── Tool: File Operations (OneLake)
     └── Tool: Custom API

This agent generates:
  1. Project scaffold (pyproject.toml, agent.yaml, src/)
  2. Agent code with Fabric Data Agent as a tool
  3. Tracing configuration (Application Insights / OpenTelemetry)
  4. Evaluation setup (batch eval, continuous eval)
  5. Deployment config (Docker, Foundry hosted, or container apps)

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/foundry-agent-builder",
    "version": "1.0.0",
    "display_name": "Foundry Agent Builder",
    "description": (
        "Scaffold Microsoft Agent Framework projects that use Fabric Data Agents "
        "as tools. Configure tracing, evaluation, and deploy to Microsoft Foundry. "
        "Generates production-ready agent code with proper auth and tool integration."
    ),
    "author": "Kody",
    "tags": ["foundry", "agent-framework", "fabric", "data-agent", "tracing", "evaluation"],
    "category": "ai",
    "quality_tier": "community",
    "dependencies": ["@rapp/basic_agent"],
}


# ── Agent Framework templates ──────────────────────────────────────────────

TOOL_TYPES = {
    "fabric_data_agent": {
        "display": "Fabric Data Agent",
        "description": "Natural language data queries via Fabric",
        "import": "from azure.ai.projects.tools import FabricDataAgentTool",
    },
    "bing_grounding": {
        "display": "Bing Grounding",
        "description": "Web search for real-time information",
        "import": "from azure.ai.projects.tools import BingGroundingTool",
    },
    "code_interpreter": {
        "display": "Code Interpreter",
        "description": "Execute Python code for calculations/charts",
        "import": "from azure.ai.projects.tools import CodeInterpreterTool",
    },
    "file_search": {
        "display": "File Search (OneLake)",
        "description": "Search through documents in OneLake",
        "import": "from azure.ai.projects.tools import FileSearchTool",
    },
    "custom_function": {
        "display": "Custom Function",
        "description": "Any Python function as a tool",
        "import": "from azure.ai.projects.tools import FunctionTool",
    },
}

EVAL_METRICS = {
    "groundedness": "How grounded is the response in the source data?",
    "relevance": "How relevant is the response to the user's question?",
    "coherence": "How coherent and well-structured is the response?",
    "fluency": "How natural and grammatically correct is the response?",
    "sql_correctness": "Does the generated SQL correctly answer the question?",
}

# ── Microsoft Best Practices for Foundry / Agent Framework ─────────────────

BEST_PRACTICES = {
    "agent_lifecycle": [
        "Follow the lifecycle: Choose type → Create → Add tools → Save versions → Debug with tracing → Evaluate → Publish → Monitor",
        "Save agent versions at each milestone — enables rollback and comparison",
        "Use agent.yaml for declarative agent definition (infrastructure as code)",
        "Test locally with Docker before deploying to Foundry hosted infrastructure",
        "Use evaluation runs to validate changes before publishing new versions",
    ],
    "tracing_and_observability": [
        "Enable native tracing integrations (Agent Framework + Semantic Kernel — no code changes needed)",
        "Use consistent span attributes across all agents (agent_name, version, environment)",
        "Correlate evaluation run IDs with trace spans for debugging failures",
        "Redact sensitive content (PII, secrets) from span attributes and logs",
        "Treat traces as production telemetry — store in Application Insights with appropriate retention",
        "Monitor latency percentiles (P50, P95, P99) per tool call and overall agent response",
    ],
    "security": [
        "NEVER store secrets in prompts, tool arguments, or span attributes",
        "Use Microsoft Entra ID (Managed Identity) for all Azure service authentication",
        "Redact PII in traces and evaluation datasets",
        "Apply AI guardrails: grounding in reliable data, hallucination filters, tool enforcement",
        "Use content safety filters on model outputs (Azure AI Content Safety)",
        "Rotate API keys and connection strings via Azure Key Vault",
    ],
    "evaluation": [
        "Run batch evaluation with curated datasets before publishing",
        "Use built-in metrics: groundedness, relevance, coherence, fluency",
        "Add custom metrics for domain-specific quality (e.g., SQL correctness)",
        "Set up continuous evaluation for production monitoring (scheduled runs)",
        "Compare evaluation results across versions to detect regressions",
        "Use evaluation comparison tool for side-by-side analysis",
    ],
    "tool_design": [
        "Each tool should have a clear, single responsibility",
        "Write detailed tool descriptions — the LLM uses them to decide when to invoke",
        "Return structured data from tools (not raw text) when possible",
        "Handle tool failures gracefully — return error info the agent can use",
        "Fabric Data Agent is the preferred tool for data queries (secure, governed)",
        "Limit tool count per agent to reduce hallucinated tool calls",
    ],
    "deployment": [
        "Use Foundry Hosted for simple agents (no infrastructure management)",
        "Use Container Apps for agents needing custom dependencies or scaling",
        "Include health check endpoints in containerized agents",
        "Set appropriate concurrency limits based on tool latency",
        "Use deployment slots for blue/green deployments",
        "Monitor cost per invocation and set budget alerts",
    ],
}


class FoundryAgentBuilder(BasicAgent):
    """Scaffolds and deploys Microsoft Agent Framework projects using Fabric Data Agents."""

    def __init__(self):
        self.name = "foundry_agent_builder"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "scaffold_project", "add_data_agent_tool", "configure_tracing",
                            "add_evaluation", "generate_agent_yaml", "deploy",
                            "full_setup", "list_tools", "best_practices",
                        ],
                        "description": "Action to perform",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Name of the agent project",
                    },
                    "agent_name": {
                        "type": "string",
                        "description": "Display name for the Foundry agent",
                    },
                    "data_agent_workspace": {
                        "type": "string",
                        "description": "Fabric workspace containing the Data Agent",
                    },
                    "data_agent_name": {
                        "type": "string",
                        "description": "Fabric Data Agent to use as a tool",
                    },
                    "tools": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(TOOL_TYPES.keys())},
                        "description": "Tools to include in the agent",
                    },
                    "model": {
                        "type": "string",
                        "description": "Model deployment name (e.g. gpt-4o, gpt-4o-mini)",
                        "default": "gpt-4o",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "System instructions for the agent",
                    },
                    "deploy_target": {
                        "type": "string",
                        "enum": ["foundry_hosted", "container_apps", "docker_local"],
                        "description": "Deployment target",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "list_tools")
        project_name = kwargs.get("project_name", "fabric-data-agent")
        agent_name = kwargs.get("agent_name", "Data Analyst Agent")
        data_agent_workspace = kwargs.get("data_agent_workspace", "demo-workspace")
        data_agent_name = kwargs.get("data_agent_name", "data-agent-demo")
        tools = kwargs.get("tools", ["fabric_data_agent"])
        model = kwargs.get("model", "gpt-4o")
        instructions = kwargs.get("instructions", "")
        deploy_target = kwargs.get("deploy_target", "foundry_hosted")

        handlers = {
            "list_tools": lambda: self._list_tools(),
            "scaffold_project": lambda: self._scaffold_project(project_name, agent_name, model, tools, instructions),
            "add_data_agent_tool": lambda: self._add_data_agent_tool(
                project_name, data_agent_workspace, data_agent_name
            ),
            "configure_tracing": lambda: self._configure_tracing(project_name),
            "add_evaluation": lambda: self._add_evaluation(project_name, data_agent_name),
            "generate_agent_yaml": lambda: self._generate_agent_yaml(
                project_name, agent_name, model, tools, instructions, deploy_target
            ),
            "deploy": lambda: self._deploy(project_name, agent_name, deploy_target),
            "full_setup": lambda: self._full_setup(
                project_name, agent_name, data_agent_workspace, data_agent_name,
                tools, model, instructions, deploy_target
            ),
            "best_practices": lambda: self._best_practices(),
        }

        handler = handlers.get(action)
        if handler:
            return handler()
        return f"Unknown action: {action}"

    # ── Handlers ───────────────────────────────────────────────────────────

    def _list_tools(self):
        lines = ["# Available Agent Tools\n"]
        for key, tool in TOOL_TYPES.items():
            lines.append(f"### {tool['display']} (`{key}`)")
            lines.append(f"{tool['description']}\n")
            lines.append(f"```python\n{tool['import']}\n```\n")
        return "\n".join(lines)

    def _scaffold_project(self, project_name, agent_name, model, tools, instructions):
        if not instructions:
            instructions = (
                "You are a data analyst assistant. Use the Fabric Data Agent tool to answer "
                "questions about data. Present results clearly with tables and summaries. "
                "If you're unsure about a query, ask clarifying questions."
            )

        pyproject = (
            f'[project]\n'
            f'name = "{project_name}"\n'
            f'version = "0.1.0"\n'
            f'description = "Foundry agent with Fabric Data Agent tool"\n'
            f'requires-python = ">=3.10"\n'
            f'dependencies = [\n'
            f'    "azure-ai-projects>=1.0.0",\n'
            f'    "azure-identity>=1.15.0",\n'
            f'    "opentelemetry-sdk>=1.20.0",\n'
            f'    "azure-monitor-opentelemetry>=1.2.0",\n'
            f']\n'
        )

        main_agent = (
            f'"""Main agent entrypoint for {agent_name}."""\n\n'
            f'import os\n'
            f'from azure.identity import DefaultAzureCredential\n'
            f'from azure.ai.projects import AIProjectClient\n'
            f'from azure.ai.projects.models import Agent, AgentThread\n\n'
            f'# Tool imports\n'
        )
        for t in tools:
            if t in TOOL_TYPES:
                main_agent += f'{TOOL_TYPES[t]["import"]}\n'

        main_agent += (
            f'\n\n'
            f'# Configuration\n'
            f'PROJECT_CONNECTION = os.environ.get("FOUNDRY_PROJECT_CONNECTION",\n'
            f'    "<your-foundry-project-connection-string>")\n'
            f'MODEL_DEPLOYMENT = "{model}"\n\n'
            f'INSTRUCTIONS = """{instructions}"""\n\n\n'
            f'def create_agent():\n'
            f'    """Create the Foundry agent with tools."""\n'
            f'    credential = DefaultAzureCredential()\n'
            f'    client = AIProjectClient.from_connection_string(\n'
            f'        conn_str=PROJECT_CONNECTION,\n'
            f'        credential=credential\n'
            f'    )\n\n'
            f'    # Configure tools\n'
            f'    tools = []\n'
        )

        if "fabric_data_agent" in tools:
            main_agent += (
                f'    # Fabric Data Agent tool\n'
                f'    fabric_tool = FabricDataAgentTool(\n'
                f'        workspace_id=os.environ["FABRIC_WORKSPACE_ID"],\n'
                f'        agent_id=os.environ["FABRIC_DATA_AGENT_ID"],\n'
                f'    )\n'
                f'    tools.append(fabric_tool)\n\n'
            )
        if "bing_grounding" in tools:
            main_agent += (
                f'    # Bing grounding for real-time data\n'
                f'    bing_tool = BingGroundingTool(\n'
                f'        connection_id=os.environ.get("BING_CONNECTION_ID", "")\n'
                f'    )\n'
                f'    tools.append(bing_tool)\n\n'
            )
        if "code_interpreter" in tools:
            main_agent += (
                f'    # Code interpreter for calculations\n'
                f'    code_tool = CodeInterpreterTool()\n'
                f'    tools.append(code_tool)\n\n'
            )

        main_agent += (
            f'    # Create agent\n'
            f'    agent = client.agents.create_agent(\n'
            f'        model=MODEL_DEPLOYMENT,\n'
            f'        name="{agent_name}",\n'
            f'        instructions=INSTRUCTIONS,\n'
            f'        tools=[t.definitions for t in tools],\n'
            f'        tool_resources={{t.resource_type: t.resources for t in tools if hasattr(t, "resources")}},\n'
            f'    )\n'
            f'    print(f"Agent created: {{agent.id}}")\n'
            f'    return client, agent\n\n\n'
            f'def run_conversation(client, agent, user_message: str):\n'
            f'    """Run a single conversation turn."""\n'
            f'    thread = client.agents.create_thread()\n'
            f'    client.agents.create_message(\n'
            f'        thread_id=thread.id,\n'
            f'        role="user",\n'
            f'        content=user_message\n'
            f'    )\n'
            f'    run = client.agents.create_and_process_run(\n'
            f'        thread_id=thread.id,\n'
            f'        agent_id=agent.id\n'
            f'    )\n'
            f'    messages = client.agents.list_messages(thread_id=thread.id)\n'
            f'    return messages.data[0].content[0].text.value\n\n\n'
            f'if __name__ == "__main__":\n'
            f'    client, agent = create_agent()\n'
            f'    response = run_conversation(client, agent, "What were total sales last quarter?")\n'
            f'    print(response)\n'
        )

        return (
            f"## Project Scaffold: `{project_name}`\n\n"
            f"### Directory Structure\n"
            f"```\n"
            f"{project_name}/\n"
            f"├── pyproject.toml\n"
            f"├── agent.yaml\n"
            f"├── Dockerfile\n"
            f"├── .env.example\n"
            f"├── src/\n"
            f"│   ├── __init__.py\n"
            f"│   ├── agent.py          ← Main agent code\n"
            f"│   ├── tools/\n"
            f"│   │   ├── __init__.py\n"
            f"│   │   └── data_agent.py ← Fabric Data Agent tool wrapper\n"
            f"│   └── config.py\n"
            f"├── eval/\n"
            f"│   ├── dataset.jsonl\n"
            f"│   └── run_eval.py\n"
            f"└── tests/\n"
            f"    └── test_agent.py\n"
            f"```\n\n"
            f"### `pyproject.toml`\n\n"
            f"```toml\n{pyproject}\n```\n\n"
            f"### `src/agent.py`\n\n"
            f"```python\n{main_agent}\n```\n\n"
            f"### `.env.example`\n\n"
            f"```env\n"
            f"FOUNDRY_PROJECT_CONNECTION=<project-connection-string>\n"
            f"FABRIC_WORKSPACE_ID=<workspace-id>\n"
            f"FABRIC_DATA_AGENT_ID=<data-agent-id>\n"
            f"AZURE_TENANT_ID={TARGET_M365_TENANT['tenant_id']}\n"
            f"APPLICATIONINSIGHTS_CONNECTION_STRING=<appinsights-conn>\n"
            f"```\n"
        )

    def _add_data_agent_tool(self, project_name, data_agent_workspace, data_agent_name):
        tool_code = (
            f'"""\n'
            f'Custom tool wrapper for Fabric Data Agent: {data_agent_name}\n'
            f'Workspace: {data_agent_workspace}\n'
            f'"""\n\n'
            f'import os\n'
            f'import requests\n'
            f'from azure.identity import DefaultAzureCredential\n\n\n'
            f'class FabricDataAgentTool:\n'
            f'    """Tool that queries a Fabric Data Agent via REST API."""\n\n'
            f'    def __init__(self, workspace_id: str = None, agent_id: str = None):\n'
            f'        self.workspace_id = workspace_id or os.environ["FABRIC_WORKSPACE_ID"]\n'
            f'        self.agent_id = agent_id or os.environ["FABRIC_DATA_AGENT_ID"]\n'
            f'        self.credential = DefaultAzureCredential()\n'
            f'        self.base_url = "https://api.fabric.microsoft.com/v1"\n\n'
            f'    @property\n'
            f'    def definitions(self):\n'
            f'        """OpenAI function-calling definition."""\n'
            f'        return {{\n'
            f'            "type": "function",\n'
            f'            "function": {{\n'
            f'                "name": "query_data",\n'
            f'                "description": "Query data using natural language. Ask any analytical question.",\n'
            f'                "parameters": {{\n'
            f'                    "type": "object",\n'
            f'                    "properties": {{\n'
            f'                        "question": {{\n'
            f'                            "type": "string",\n'
            f'                            "description": "Natural language question about the data"\n'
            f'                        }}\n'
            f'                    }},\n'
            f'                    "required": ["question"]\n'
            f'                }}\n'
            f'            }}\n'
            f'        }}\n\n'
            f'    def execute(self, question: str) -> dict:\n'
            f'        """Call the Fabric Data Agent API."""\n'
            f'        token = self.credential.get_token("{SCOPES["fabric"]}").token\n'
            f'        headers = {{\n'
            f'            "Authorization": f"Bearer {{token}}",\n'
            f'            "Content-Type": "application/json"\n'
            f'        }}\n'
            f'        resp = requests.post(\n'
            f'            f"{{self.base_url}}/workspaces/{{self.workspace_id}}/dataAgents/{{self.agent_id}}/query",\n'
            f'            headers=headers,\n'
            f'            json={{"question": question}}\n'
            f'        )\n'
            f'        resp.raise_for_status()\n'
            f'        return resp.json()\n'
        )

        return (
            f"## Fabric Data Agent Tool: `{data_agent_name}`\n\n"
            f"### `src/tools/data_agent.py`\n\n"
            f"```python\n{tool_code}\n```\n\n"
            f"### Usage in Agent\n\n"
            f"```python\n"
            f"from tools.data_agent import FabricDataAgentTool\n\n"
            f"data_tool = FabricDataAgentTool()\n"
            f"result = data_tool.execute(\"What were total sales last quarter?\")\n"
            f"print(result)\n"
            f"```\n\n"
            f"### Environment Variables Required\n"
            f"- `FABRIC_WORKSPACE_ID` — get from `fabric_data_agent_builder` agent\n"
            f"- `FABRIC_DATA_AGENT_ID` — get from `fabric_data_agent_builder` agent\n"
        )

    def _configure_tracing(self, project_name):
        tracing_code = (
            f'"""Configure OpenTelemetry tracing for the Foundry agent."""\n\n'
            f'import os\n'
            f'from opentelemetry import trace\n'
            f'from opentelemetry.sdk.trace import TracerProvider\n'
            f'from opentelemetry.sdk.trace.export import BatchSpanProcessor\n'
            f'from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter\n\n\n'
            f'def setup_tracing():\n'
            f'    """Initialize tracing with Application Insights."""\n'
            f'    conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")\n'
            f'    if not conn_str:\n'
            f'        print("Warning: No Application Insights connection string. Tracing disabled.")\n'
            f'        return\n\n'
            f'    exporter = AzureMonitorTraceExporter(connection_string=conn_str)\n'
            f'    provider = TracerProvider()\n'
            f'    provider.add_span_processor(BatchSpanProcessor(exporter))\n'
            f'    trace.set_tracer_provider(provider)\n'
            f'    print("Tracing configured → Application Insights")\n\n\n'
            f'def trace_agent_call(func):\n'
            f'    """Decorator to trace agent tool calls."""\n'
            f'    def wrapper(*args, **kwargs):\n'
            f'        tracer = trace.get_tracer(__name__)\n'
            f'        with tracer.start_as_current_span(\n'
            f'            func.__name__,\n'
            f'            attributes={{\n'
            f'                "agent.tool": func.__name__,\n'
            f'                "agent.project": "{project_name}",\n'
            f'            }}\n'
            f'        ) as span:\n'
            f'            try:\n'
            f'                result = func(*args, **kwargs)\n'
            f'                span.set_attribute("agent.status", "success")\n'
            f'                return result\n'
            f'            except Exception as e:\n'
            f'                span.set_attribute("agent.status", "error")\n'
            f'                span.record_exception(e)\n'
            f'                raise\n'
            f'    return wrapper\n'
        )

        return (
            f"## Tracing Configuration: `{project_name}`\n\n"
            f"### `src/tracing.py`\n\n"
            f"```python\n{tracing_code}\n```\n\n"
            f"### Integration with Agent\n\n"
            f"```python\n"
            f"from tracing import setup_tracing, trace_agent_call\n\n"
            f"# Call at startup\n"
            f"setup_tracing()\n\n"
            f"# Decorate tool calls\n"
            f"@trace_agent_call\n"
            f"def query_data(question: str):\n"
            f"    return data_tool.execute(question)\n"
            f"```\n\n"
            f"### What Gets Traced\n"
            f"- Each user message → agent response (latency, tokens)\n"
            f"- Each tool call (Fabric Data Agent queries)\n"
            f"- Errors and exceptions\n"
            f"- Custom attributes (question, SQL generated, row count)\n\n"
            f"### View Traces\n"
            f"- **Foundry Portal** → Project → Tracing\n"
            f"- **Application Insights** → Transaction search\n"
            f"- **VS Code** → AI Toolkit → Traces\n"
        )

    def _add_evaluation(self, project_name, data_agent_name):
        eval_dataset = [
            {"question": "What were total sales last quarter?", "expected_sql_contains": "SUM", "expected_tables": ["fact_sales"]},
            {"question": "Top 10 customers by revenue", "expected_sql_contains": "ORDER BY", "expected_tables": ["fact_sales", "dim_customer"]},
            {"question": "Month-over-month growth", "expected_sql_contains": "LAG", "expected_tables": ["fact_sales"]},
        ]

        eval_code = (
            f'"""Evaluation runner for {project_name}."""\n\n'
            f'import json\n'
            f'from azure.ai.projects import AIProjectClient\n'
            f'from azure.identity import DefaultAzureCredential\n'
            f'from azure.ai.evaluation import (\n'
            f'    GroundednessEvaluator,\n'
            f'    RelevanceEvaluator,\n'
            f'    CoherenceEvaluator,\n'
            f')\n\n\n'
            f'def run_batch_eval(dataset_path: str = "eval/dataset.jsonl"):\n'
            f'    """Run batch evaluation against the agent."""\n'
            f'    credential = DefaultAzureCredential()\n'
            f'    \n'
            f'    # Load dataset\n'
            f'    with open(dataset_path) as f:\n'
            f'        dataset = [json.loads(line) for line in f]\n\n'
            f'    # Initialize evaluators\n'
            f'    evaluators = {{\n'
            f'        "groundedness": GroundednessEvaluator(),\n'
            f'        "relevance": RelevanceEvaluator(),\n'
            f'        "coherence": CoherenceEvaluator(),\n'
            f'    }}\n\n'
            f'    results = []\n'
            f'    for item in dataset:\n'
            f'        # Call agent\n'
            f'        response = call_agent(item["question"])\n'
            f'        \n'
            f'        # Evaluate\n'
            f'        scores = {{}}\n'
            f'        for name, evaluator in evaluators.items():\n'
            f'            score = evaluator(\n'
            f'                query=item["question"],\n'
            f'                response=response,\n'
            f'            )\n'
            f'            scores[name] = score\n'
            f'        \n'
            f'        results.append({{\n'
            f'            "question": item["question"],\n'
            f'            "response": response,\n'
            f'            "scores": scores\n'
            f'        }})\n\n'
            f'    # Print summary\n'
            f'    print(f"Evaluated {{len(results)}} questions")\n'
            f'    for metric in evaluators:\n'
            f'        avg = sum(r["scores"][metric] for r in results) / len(results)\n'
            f'        print(f"  {{metric}}: {{avg:.2f}}")\n\n'
            f'    return results\n\n\n'
            f'if __name__ == "__main__":\n'
            f'    run_batch_eval()\n'
        )

        return (
            f"## Evaluation Setup: `{project_name}`\n\n"
            f"### `eval/dataset.jsonl`\n\n"
            f"```jsonl\n"
            + "\n".join(json.dumps(item) for item in eval_dataset)
            + f"\n```\n\n"
            f"### `eval/run_eval.py`\n\n"
            f"```python\n{eval_code}\n```\n\n"
            f"### Evaluation Metrics\n\n"
            f"| Metric | What It Measures |\n"
            f"|--------|------------------|\n"
            + "\n".join(f"| {k} | {v} |" for k, v in EVAL_METRICS.items())
            + f"\n\n### Continuous Evaluation\n"
            f"Set up continuous eval in Foundry to monitor agent quality over time:\n\n"
            f"```bash\n"
            f"# Via Foundry CLI\n"
            f"az ai foundry evaluation create \\\n"
            f"  --name \"{project_name}-continuous\" \\\n"
            f"  --agent-id <agent-id> \\\n"
            f"  --schedule \"0 */6 * * *\" \\\n"
            f"  --evaluators groundedness,relevance,coherence\n"
            f"```\n"
        )

    def _generate_agent_yaml(self, project_name, agent_name, model, tools, instructions, deploy_target):
        if not instructions:
            instructions = (
                "You are a data analyst assistant. Use tools to answer data questions accurately."
            )

        agent_yaml = {
            "name": agent_name,
            "model": model,
            "instructions": instructions,
            "tools": [],
            "deployment": {
                "type": deploy_target,
            },
        }

        for t in tools:
            if t == "fabric_data_agent":
                agent_yaml["tools"].append({
                    "type": "fabric_data_agent",
                    "config": {
                        "workspace_id": "${FABRIC_WORKSPACE_ID}",
                        "agent_id": "${FABRIC_DATA_AGENT_ID}",
                    }
                })
            elif t == "bing_grounding":
                agent_yaml["tools"].append({
                    "type": "bing_grounding",
                    "config": {"connection_id": "${BING_CONNECTION_ID}"}
                })
            elif t == "code_interpreter":
                agent_yaml["tools"].append({"type": "code_interpreter"})

        return (
            f"## Agent Configuration: `agent.yaml`\n\n"
            f"```yaml\n"
            f"# agent.yaml for {project_name}\n"
            f"name: \"{agent_name}\"\n"
            f"model: {model}\n"
            f"instructions: |\n"
            f"  {instructions}\n"
            f"tools:\n"
            + "\n".join(f"  - type: {t}" for t in tools)
            + f"\ndeployment:\n"
            f"  type: {deploy_target}\n"
            f"  environment:\n"
            f"    FABRIC_WORKSPACE_ID: ${{{{FABRIC_WORKSPACE_ID}}}}\n"
            f"    FABRIC_DATA_AGENT_ID: ${{{{FABRIC_DATA_AGENT_ID}}}}\n"
            f"    AZURE_TENANT_ID: {TARGET_M365_TENANT['tenant_id']}\n"
            f"```\n"
        )

    def _deploy(self, project_name, agent_name, deploy_target):
        lines = [f"## Deploy: `{project_name}` → {deploy_target}\n"]

        if deploy_target == "foundry_hosted":
            lines.extend([
                "### Foundry Hosted Agent (Simplest)\n",
                "```bash\n",
                "# Login to Azure\n",
                f"az login --tenant {TARGET_M365_TENANT['tenant_id']}\n\n",
                "# Create/update the agent in Foundry\n",
                "az ai foundry agent create \\\n",
                f"  --name \"{agent_name}\" \\\n",
                "  --project <project-name> \\\n",
                "  --model gpt-4o \\\n",
                "  --instructions-file src/instructions.txt \\\n",
                "  --tools fabric_data_agent,code_interpreter\n",
                "```\n\n",
                "**Pros:** No infra to manage, auto-scaling, built-in tracing\n",
                "**Cons:** Limited customization, can't run arbitrary code\n",
            ])
        elif deploy_target == "container_apps":
            lines.extend([
                "### Azure Container Apps (Full control)\n",
                "```bash\n",
                "# Build container\n",
                f"docker build -t {project_name}:latest .\n\n",
                "# Push to ACR\n",
                f"az acr build --registry <acr-name> --image {project_name}:latest .\n\n",
                "# Deploy to Container Apps\n",
                f"az containerapp create \\\n",
                f"  --name {project_name} \\\n",
                "  --resource-group <rg> \\\n",
                "  --image <acr-name>.azurecr.io/" + project_name + ":latest \\\n",
                "  --env-vars \\\n",
                f"    AZURE_TENANT_ID={TARGET_M365_TENANT['tenant_id']} \\\n",
                "    FABRIC_WORKSPACE_ID=<ws-id> \\\n",
                "    FABRIC_DATA_AGENT_ID=<agent-id>\n",
                "```\n\n",
                "**Pros:** Full code control, custom tools, scale-to-zero\n",
                "**Cons:** More setup, manage container lifecycle\n",
            ])
        elif deploy_target == "docker_local":
            lines.extend([
                "### Docker (Local Development)\n",
                f"```dockerfile\n",
                f"# Dockerfile\n",
                f"FROM python:3.12-slim\n",
                f"WORKDIR /app\n",
                f"COPY pyproject.toml .\n",
                f"RUN pip install .\n",
                f"COPY src/ src/\n",
                f"CMD [\"python\", \"-m\", \"src.agent\"]\n",
                f"```\n\n",
                f"```bash\n",
                f"docker build -t {project_name} .\n",
                f"docker run --env-file .env {project_name}\n",
                f"```\n",
            ])

        return "\n".join(lines)

    def _full_setup(self, project_name, agent_name, data_agent_workspace, data_agent_name,
                    tools, model, instructions, deploy_target):
        sections = [
            f"# Full Foundry Agent Setup: `{project_name}`\n",
            f"**Agent:** {agent_name}\n",
            f"**Data Source:** {data_agent_name} (in {data_agent_workspace})\n",
            f"**Model:** {model}\n",
            f"**Deploy:** {deploy_target}\n\n---\n",
            self._scaffold_project(project_name, agent_name, model, tools, instructions),
            "\n---\n",
            self._add_data_agent_tool(project_name, data_agent_workspace, data_agent_name),
            "\n---\n",
            self._configure_tracing(project_name),
            "\n---\n",
            self._add_evaluation(project_name, data_agent_name),
            "\n---\n",
            self._generate_agent_yaml(project_name, agent_name, model, tools, instructions, deploy_target),
            "\n---\n",
            self._deploy(project_name, agent_name, deploy_target),
            "\n---\n",
            "## Integration Summary\n\n"
            "```\n"
            f"[User] → [Foundry Agent: {agent_name}]\n"
            f"              │\n"
            f"              ├─ Tool: Fabric Data Agent ({data_agent_name})\n"
            f"              │      └─ NL → SQL → Results from Lakehouse\n"
            f"              ├─ Tool: Code Interpreter\n"
            f"              │      └─ Charts, calculations\n"
            f"              └─ Tracing → Application Insights\n"
            "```\n",
        ]
        return "\n".join(sections)

    def _best_practices(self):
        lines = ["# Microsoft Foundry / Agent Framework — Best Practices\n"]
        lines.append("*Source: Microsoft Learn documentation (2025)*\n")
        for category, practices in BEST_PRACTICES.items():
            lines.append(f"\n## {category.replace('_', ' ').title()}\n")
            for p in practices:
                lines.append(f"- {p}")
        lines.append("\n\n## Agent Lifecycle Diagram\n")
        lines.append("```")
        lines.append("[1. Choose] → [2. Create] → [3. Add Tools] → [4. Save Version]")
        lines.append("                                                      │")
        lines.append("                                                      ▼")
        lines.append("[7. Monitor] ← [6. Publish] ← [5. Debug+Trace] → [Evaluate]")
        lines.append("     │                                                 │")
        lines.append("     └─── Continuous Eval ◄────────────────────────────┘")
        lines.append("```")
        lines.append(f"\n📖 Docs: https://learn.microsoft.com/azure/ai-foundry/concepts/agents")
        return "\n".join(lines)
