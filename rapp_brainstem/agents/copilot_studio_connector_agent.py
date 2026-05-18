"""
Copilot Studio Connector Agent — wires Microsoft Copilot Studio custom copilots
to Fabric Data Agents, configures authentication (SSO/OAuth), generates plugin
manifests, and creates declarative agent packages for M365 Copilot.

Integration paths:
  1. Copilot Studio → Fabric Data Agent (plugin action)
  2. Copilot Studio → M365 Copilot (declarative agent)
  3. Copilot Studio → Power Automate → any backend
  4. Copilot Studio → Custom connector → REST API

This agent generates the configuration and code needed for each path.

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES, get_fabric_auth_preamble


# ── Copilot Studio channel types ──────────────────────────────────────────

CHANNELS = {
    "teams": {"display": "Microsoft Teams", "icon": "💬"},
    "web": {"display": "Web Chat (embed)", "icon": "🌐"},
    "m365_copilot": {"display": "Microsoft 365 Copilot", "icon": "✨"},
    "power_apps": {"display": "Power Apps", "icon": "📱"},
    "dynamics365": {"display": "Dynamics 365", "icon": "🏢"},
    "custom_website": {"display": "Custom Website (Direct Line)", "icon": "🔗"},
}

# ── Auth configurations ────────────────────────────────────────────────────

AUTH_CONFIGS = {
    "sso_entra": {
        "display": "SSO with Microsoft Entra ID",
        "description": "User signs in once; token flows through to Fabric Data Agent",
        "recommended_for": ["teams", "m365_copilot", "power_apps"],
    },
    "oauth_delegated": {
        "display": "OAuth 2.0 (Delegated)",
        "description": "User consents to permissions; agent acts on behalf of user",
        "recommended_for": ["web", "custom_website"],
    },
    "service_principal": {
        "display": "Service Principal (App-only)",
        "description": "Agent authenticates as an app; no user context",
        "recommended_for": ["power_automate", "background_jobs"],
    },
}

# ── Plugin action types ────────────────────────────────────────────────────

PLUGIN_TYPES = {
    "fabric_data_agent": "Query data via Fabric Data Agent (natural language → SQL)",
    "http_action": "Call any REST API endpoint",
    "power_automate_flow": "Trigger a Power Automate flow",
    "connector": "Use a pre-built or custom connector",
    "knowledge": "Ground the copilot with a Knowledge source",
}

# ── Microsoft Best Practices for Copilot Studio ───────────────────────────

BEST_PRACTICES = {
    "security_and_identity": [
        "Authenticate with Microsoft Entra ID (default secure setting) — don't disable",
        "Use end-user credentials for connectors — agent acts on behalf of the signed-in user",
        "Security scan runs before publishing; warns if secure defaults are changed",
        "License access via Entra ID security groups (not individual user assignment)",
        "Apply sensitivity labels that flow through to copilot responses",
        "Store secrets (API keys, connection strings) in Azure Key Vault — never in topics",
    ],
    "access_and_governance": [
        "Manage copilot access via Entra ID groups (not individual assignments)",
        "Group Teams for security roles — map to workspace roles",
        "Apply restrictive data loss prevention (DLP) policies to limit knowledge sources",
        "Use gated release process: Dev → Test → Production (separate environments)",
        "Enable audit logging for compliance and usage tracking",
        "Review and approve before publishing to production channels",
    ],
    "data_agent_integration": [
        "Use Fabric Data Agents as the preferred data path (NL → SQL, secure by design)",
        "Data Agent uses the calling user's identity — no shared service accounts",
        "Row-Level Security on the data source applies automatically",
        "Test common questions through Data Agent before wiring to Copilot Studio",
        "Provide fallback topics when Data Agent returns no results",
        "Configure verified answers for critical business questions",
    ],
    "copilot_design": [
        "Define clear scope — what the copilot CAN and CANNOT answer",
        "Use system topics for greeting, escalation, and fallback",
        "Keep topic count manageable — merge overlapping topics",
        "Use generative answers (GPT) for long-tail questions outside defined topics",
        "Test with real users before broad rollout — collect feedback",
        "Use conversation transcripts to improve topics iteratively",
    ],
    "channels_and_deployment": [
        "Teams is the primary enterprise channel — start there",
        "For M365 Copilot, create a declarative agent package",
        "Web chat: embed with authentication (don't expose unauthenticated endpoints)",
        "Monitor channel-specific usage metrics in Copilot Studio Analytics",
        "Use adaptive cards for rich responses in Teams",
    ],
}


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/copilot-studio-connector",
    "version": "1.0.0",
    "display_name": "Copilot Studio Connector Agent",
    "description": (
        "Connect Microsoft Copilot Studio to Fabric Data Agents, configure SSO/OAuth, "
        "generate plugin manifests, and create M365 Copilot declarative agents. "
        "Supports Teams, web, M365 Copilot, and custom website channels."
    ),
    "author": "Kody",
    "tags": ["copilot-studio", "fabric", "data-agent", "m365", "teams", "plugin", "sso"],
    "category": "ai",
    "quality_tier": "community",
    "dependencies": ["@rapp/basic_agent"],
}


class CopilotStudioConnectorAgent(BasicAgent):
    """Connects Copilot Studio copilots to Fabric Data Agents and other backends."""

    def __init__(self):
        self.name = "copilot_studio_connector"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "create_copilot", "add_data_agent_plugin", "configure_auth",
                            "add_channel", "create_declarative_agent", "generate_manifest",
                            "full_setup", "list_options", "best_practices",
                        ],
                        "description": "Action to perform",
                    },
                    "copilot_name": {
                        "type": "string",
                        "description": "Name of the Copilot Studio copilot",
                    },
                    "data_agent_name": {
                        "type": "string",
                        "description": "Name of the Fabric Data Agent to connect",
                    },
                    "workspace": {
                        "type": "string",
                        "description": "Fabric workspace containing the Data Agent",
                    },
                    "channel": {
                        "type": "string",
                        "enum": list(CHANNELS.keys()),
                        "description": "Channel to deploy the copilot to",
                    },
                    "auth_type": {
                        "type": "string",
                        "enum": list(AUTH_CONFIGS.keys()),
                        "description": "Authentication configuration",
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of what the copilot does",
                    },
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Topics/intents the copilot handles",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "list_options")
        copilot_name = kwargs.get("copilot_name", "data-copilot")
        data_agent_name = kwargs.get("data_agent_name", "data-agent-demo")
        workspace = kwargs.get("workspace", "demo-workspace")
        channel = kwargs.get("channel", "teams")
        auth_type = kwargs.get("auth_type", "sso_entra")
        description = kwargs.get("description", "Ask questions about your data in natural language")
        topics = kwargs.get("topics", [])

        handlers = {
            "list_options": lambda: self._list_options(),
            "create_copilot": lambda: self._create_copilot(copilot_name, description, workspace),
            "add_data_agent_plugin": lambda: self._add_data_agent_plugin(
                copilot_name, data_agent_name, workspace
            ),
            "configure_auth": lambda: self._configure_auth(copilot_name, auth_type, workspace),
            "add_channel": lambda: self._add_channel(copilot_name, channel),
            "create_declarative_agent": lambda: self._create_declarative_agent(
                copilot_name, data_agent_name, workspace, description, topics
            ),
            "generate_manifest": lambda: self._generate_manifest(
                copilot_name, data_agent_name, workspace, description
            ),
            "full_setup": lambda: self._full_setup(
                copilot_name, data_agent_name, workspace, channel, auth_type, description, topics
            ),
            "best_practices": lambda: self._best_practices(),
        }

        handler = handlers.get(action)
        if handler:
            return handler()
        return f"Unknown action: {action}"

    # ── Handlers ───────────────────────────────────────────────────────────

    def _list_options(self):
        lines = ["# Copilot Studio Integration Options\n"]

        lines.append("## Channels\n")
        for key, ch in CHANNELS.items():
            lines.append(f"- {ch['icon']} **{ch['display']}** (`{key}`)")

        lines.append("\n## Authentication Types\n")
        for key, auth in AUTH_CONFIGS.items():
            lines.append(f"- **{auth['display']}** (`{key}`)")
            lines.append(f"  {auth['description']}")
            lines.append(f"  Recommended for: {', '.join(auth['recommended_for'])}\n")

        lines.append("## Plugin Types\n")
        for key, desc in PLUGIN_TYPES.items():
            lines.append(f"- `{key}`: {desc}")

        lines.append("\n## Architecture\n")
        lines.append("```")
        lines.append("[User in Teams/Web/M365]")
        lines.append("       │")
        lines.append("       ▼")
        lines.append("[Copilot Studio Copilot]  ← Topics, Generative AI, Plugins")
        lines.append("       │")
        lines.append("       ├──▶ [Fabric Data Agent Plugin]  ← NL → SQL → Results")
        lines.append("       ├──▶ [Power Automate Flow]       ← Write-back, notifications")
        lines.append("       └──▶ [Custom Connector]          ← Any REST API")
        lines.append("```")
        return "\n".join(lines)

    def _create_copilot(self, copilot_name, description, workspace):
        return (
            f"## Create Copilot: `{copilot_name}`\n\n"
            f"### Steps in Copilot Studio\n\n"
            f"1. Go to [Copilot Studio](https://copilotstudio.microsoft.com)\n"
            f"2. **Environment:** Select your Power Platform environment (linked to EXP tenant)\n"
            f"3. **Create** → **New Copilot**\n"
            f"4. Configure:\n"
            f"   - **Name:** `{copilot_name}`\n"
            f"   - **Description:** {description}\n"
            f"   - **Language:** English\n"
            f"   - **Generative AI:** Enabled (for orchestration)\n\n"
            f"### Power Platform CLI (alternative)\n\n"
            f"```powershell\n"
            f"# Install Power Platform CLI\n"
            f"dotnet tool install --global Microsoft.PowerApps.CLI.Tool\n\n"
            f"# Authenticate to EXP tenant\n"
            f"pac auth create --tenant {TARGET_M365_TENANT['tenant_id']} --name MCAPS\n\n"
            f"# Create copilot (requires solution context)\n"
            f"pac copilot create --name \"{copilot_name}\" --description \"{description}\"\n"
            f"```\n\n"
            f"### Environment Setup\n"
            f"- Tenant: `{TARGET_M365_TENANT['tenant_id']}` (EXP)\n"
            f"- Identity: `{TARGET_M365_TENANT['login_hint']}`\n"
            f"- Requires: Copilot Studio license (included in M365 E3+)\n"
        )

    def _add_data_agent_plugin(self, copilot_name, data_agent_name, workspace):
        auth = get_fabric_auth_preamble(workspace)
        return (
            f"## Add Fabric Data Agent Plugin to `{copilot_name}`\n\n"
            f"### Option 1: Via Copilot Studio UI\n\n"
            f"1. Open `{copilot_name}` in Copilot Studio\n"
            f"2. Go to **Actions** → **Add an action**\n"
            f"3. Select **Connector** → **Microsoft Fabric Data Agent**\n"
            f"4. Configure:\n"
            f"   - **Workspace:** {workspace}\n"
            f"   - **Data Agent:** {data_agent_name}\n"
            f"   - **Auth:** Use connection (SSO passthrough)\n"
            f"5. Test with: _\"What were total sales last quarter?\"_\n\n"
            f"### Option 2: Custom HTTP Action (manual)\n\n"
            f"If the built-in connector isn't available, use an HTTP action:\n\n"
            f"1. **Actions** → **Add an action** → **HTTP Request**\n"
            f"2. Configure the request:\n\n"
            f"```yaml\n"
            f"Method: POST\n"
            f"URL: https://api.fabric.microsoft.com/v1/workspaces/<workspace-id>/dataAgents/<agent-id>/query\n"
            f"Headers:\n"
            f"  Authorization: Bearer {{{{auth.token}}}}\n"
            f"  Content-Type: application/json\n"
            f"Body:\n"
            f"  {{\"question\": \"{{{{topic.userQuestion}}}}\"}}\n"
            f"```\n\n"
            f"### Option 3: Via Power Automate (most flexible)\n\n"
            f"1. Create a Power Automate flow:\n"
            f"   - Trigger: **When Copilot calls a flow**\n"
            f"   - Input: `question` (text)\n"
            f"   - Action: HTTP → POST to Data Agent API\n"
            f"   - Output: Return the response\n"
            f"2. In Copilot Studio: **Actions** → **Call a flow** → select your flow\n\n"
            f"### Get Data Agent Endpoint\n\n"
            f"```python\n{auth}\n"
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# Find the Data Agent ID\n'
            f'resp = requests.get(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/items?type=DataAgent",\n'
            f'    headers=headers\n'
            f')\n'
            f'agents = resp.json().get("value", [])\n'
            f'for a in agents:\n'
            f'    if a["displayName"] == "{data_agent_name}":\n'
            f'        print(f"Agent ID: {{a[\'id\']}}")\n'
            f'        print(f"Endpoint: {{FABRIC_API}}/workspaces/{{workspace_id}}/dataAgents/{{a[\'id\']}}/query")\n'
            f'```\n'
        )

    def _configure_auth(self, copilot_name, auth_type, workspace):
        config = AUTH_CONFIGS.get(auth_type, AUTH_CONFIGS["sso_entra"])

        lines = [
            f"## Configure Authentication: `{copilot_name}`\n",
            f"**Type:** {config['display']}\n",
            f"**Description:** {config['description']}\n\n",
        ]

        if auth_type == "sso_entra":
            lines.extend([
                "### SSO Configuration Steps\n",
                "1. **App Registration** (Entra ID → App registrations → New)\n",
                f"   - Name: `{copilot_name}-app`\n",
                f"   - Tenant: `{TARGET_M365_TENANT['tenant_id']}`\n",
                "   - Redirect URI: `https://token.botframework.com/.auth/web/redirect`\n",
                "   - Supported account types: Single tenant\n\n",
                "2. **API Permissions** (add these delegated permissions):\n",
                f"   - `{SCOPES['fabric']}` (Fabric)\n",
                "   - `User.Read` (Graph)\n",
                "   - `openid`, `profile`, `offline_access`\n\n",
                "3. **Client Secret** (Certificates & secrets → New client secret)\n\n",
                "4. **Copilot Studio Settings** → Security → Authentication:\n",
                "   - Authentication: **Manual**\n",
                "   - Provider: **Azure Active Directory v2**\n",
                f"   - Client ID: `<from step 1>`\n",
                f"   - Tenant ID: `{TARGET_M365_TENANT['tenant_id']}`\n",
                f"   - Scopes: `{SCOPES['fabric']} openid profile`\n\n",
                "5. **Teams Channel** (for SSO in Teams):\n",
                "   - Enable **Teams SSO** in channel settings\n",
                "   - Add bot app ID to Teams app manifest\n\n",
                "### Token Flow\n",
                "```\n",
                "User (Teams) → SSO token → Copilot Studio → Exchange for Fabric token → Data Agent\n",
                "```\n",
            ])
        elif auth_type == "oauth_delegated":
            lines.extend([
                "### OAuth 2.0 Delegated Configuration\n",
                "Same as SSO but the user gets a consent prompt on first use.\n",
                "Use for web/embedded scenarios where SSO isn't available.\n\n",
                f"- Authority: `{TARGET_M365_TENANT['authority']}`\n",
                f"- Scope: `{SCOPES['fabric']}`\n",
            ])
        elif auth_type == "service_principal":
            lines.extend([
                "### Service Principal Configuration\n",
                "⚠️ No user context — the agent queries as the app, not the user.\n",
                "RLS (Row-Level Security) won't apply.\n\n",
                "Use when: background automation, system-to-system calls.\n\n",
                f"- Tenant: `{TARGET_M365_TENANT['tenant_id']}`\n",
                f"- Scope: `{SCOPES['fabric']}`\n",
                "- Grant: `Application` permissions (admin consent required)\n",
            ])

        return "\n".join(lines)

    def _add_channel(self, copilot_name, channel):
        ch = CHANNELS.get(channel, CHANNELS["teams"])
        lines = [
            f"## Deploy to Channel: {ch['icon']} {ch['display']}\n",
            f"**Copilot:** `{copilot_name}`\n\n",
        ]

        if channel == "teams":
            lines.extend([
                "### Teams Deployment\n",
                "1. In Copilot Studio → **Channels** → **Microsoft Teams**\n",
                "2. Click **Turn on Teams**\n",
                "3. **Availability:** Add to specific users or publish to org app catalog\n",
                "4. For org-wide: Submit to Teams Admin Center for approval\n\n",
                "### Teams App Manifest (for custom deployment)\n",
                "```json\n",
                json.dumps({
                    "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.16/MicrosoftTeams.schema.json",
                    "manifestVersion": "1.16",
                    "id": "<bot-app-id>",
                    "name": {"short": copilot_name},
                    "description": {"short": "AI data assistant", "full": "Ask questions about your data"},
                    "bots": [{"botId": "<bot-app-id>", "scopes": ["personal", "team", "groupChat"]}],
                }, indent=2),
                "\n```\n",
            ])
        elif channel == "m365_copilot":
            lines.extend([
                "### M365 Copilot (Declarative Agent)\n",
                "This makes your copilot available as a plugin inside Microsoft 365 Copilot.\n\n",
                "1. In Copilot Studio → **Channels** → **Microsoft 365 Copilot**\n",
                "2. Enable the declarative agent\n",
                "3. Users invoke with: `@data-copilot what were sales last quarter?`\n\n",
                "**Requirements:**\n",
                "- M365 Copilot license for end users\n",
                "- Admin approval for the plugin\n",
                "- SSO authentication configured\n",
            ])
        elif channel == "web":
            lines.extend([
                "### Web Chat Embed\n",
                "1. In Copilot Studio → **Channels** → **Custom website**\n",
                "2. Copy the embed code:\n\n",
                "```html\n",
                "<iframe\n",
                f'  src="https://web.powerva.microsoft.com/environments/<env-id>/bots/<bot-id>/webchat"\n',
                '  style="width: 400px; height: 600px; border: none;"\n',
                "></iframe>\n",
                "```\n",
            ])

        return "\n".join(lines)

    def _create_declarative_agent(self, copilot_name, data_agent_name, workspace, description, topics):
        if not topics:
            topics = [
                "Query sales data",
                "Customer analytics",
                "Product performance",
                "Generate reports",
            ]

        manifest = {
            "$schema": "https://developer.microsoft.com/json-schemas/copilot/declarative-agent/v1.0/schema.json",
            "version": "v1.0",
            "name": copilot_name,
            "description": description,
            "instructions": (
                f"You are a data analyst assistant. When users ask questions about data, "
                f"use the {data_agent_name} plugin to query the Fabric Data Agent. "
                f"Present results clearly with tables and summaries."
            ),
            "capabilities": [
                {"name": "GraphConnectors", "connections": []},
            ],
            "actions": [
                {
                    "id": f"plugin_{data_agent_name.replace('-', '_')}",
                    "file": "plugin-manifest.json",
                }
            ],
        }

        plugin_manifest = {
            "schema_version": "v2",
            "name_for_human": f"{copilot_name} Data Plugin",
            "description_for_human": f"Query {workspace} data in natural language",
            "description_for_model": (
                f"Use this plugin when the user asks questions about data, metrics, "
                f"sales, customers, or any analytical question. The plugin sends the "
                f"user's question to a Fabric Data Agent which generates SQL and returns results."
            ),
            "auth": {
                "type": "OAuthPluginVault",
                "reference_id": f"{TARGET_M365_TENANT['tenant_id']}_fabric",
            },
            "functions": [
                {
                    "name": "queryData",
                    "description": "Ask a natural language question about the data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The user's question about the data",
                            }
                        },
                        "required": ["question"],
                    },
                }
            ],
            "runtimes": [
                {
                    "type": "OpenApi",
                    "auth": {"type": "OAuthPluginVault"},
                    "spec": {
                        "url": f"https://api.fabric.microsoft.com/v1/workspaces/<workspace-id>/dataAgents/<agent-id>/openapi.json",
                    },
                }
            ],
        }

        return (
            f"## Declarative Agent for M365 Copilot: `{copilot_name}`\n\n"
            f"This creates a declarative agent that extends Microsoft 365 Copilot with "
            f"your Fabric Data Agent as a plugin.\n\n"
            f"### File: `declarativeAgent.json`\n\n"
            f"```json\n{json.dumps(manifest, indent=2)}\n```\n\n"
            f"### File: `plugin-manifest.json`\n\n"
            f"```json\n{json.dumps(plugin_manifest, indent=2)}\n```\n\n"
            f"### Deployment\n\n"
            f"1. Package both files into a Teams app (with manifest.json)\n"
            f"2. Upload to Teams Admin Center or sideload for testing\n"
            f"3. Users access via: `@{copilot_name}` in M365 Copilot\n\n"
            f"### Topics/Intents Handled\n"
            + "\n".join(f"- {t}" for t in topics)
        )

    def _generate_manifest(self, copilot_name, data_agent_name, workspace, description):
        openapi_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": f"{copilot_name} - Data Query API",
                "version": "1.0.0",
                "description": description,
            },
            "servers": [
                {"url": "https://api.fabric.microsoft.com/v1"}
            ],
            "paths": {
                "/workspaces/{workspaceId}/dataAgents/{agentId}/query": {
                    "post": {
                        "operationId": "queryData",
                        "summary": "Query data using natural language",
                        "parameters": [
                            {"name": "workspaceId", "in": "path", "required": True, "schema": {"type": "string"}},
                            {"name": "agentId", "in": "path", "required": True, "schema": {"type": "string"}},
                        ],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "question": {"type": "string", "description": "Natural language question"},
                                        },
                                        "required": ["question"],
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "Query results",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "generatedSql": {"type": "string"},
                                                "data": {"type": "array", "items": {"type": "object"}},
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    }
                }
            },
            "security": [{"oauth2": [SCOPES["fabric"]]}],
            "components": {
                "securitySchemes": {
                    "oauth2": {
                        "type": "oauth2",
                        "flows": {
                            "authorizationCode": {
                                "authorizationUrl": f"{TARGET_M365_TENANT['authority']}/oauth2/v2.0/authorize",
                                "tokenUrl": f"{TARGET_M365_TENANT['authority']}/oauth2/v2.0/token",
                                "scopes": {SCOPES["fabric"]: "Access Fabric APIs"},
                            }
                        },
                    }
                }
            },
        }

        return (
            f"## OpenAPI Manifest: `{copilot_name}`\n\n"
            f"Use this spec to register the Fabric Data Agent as a custom connector "
            f"in Copilot Studio or Power Platform.\n\n"
            f"### File: `openapi-spec.json`\n\n"
            f"```json\n{json.dumps(openapi_spec, indent=2)}\n```\n\n"
            f"### Import into Copilot Studio\n"
            f"1. **Actions** → **Add an action** → **New action** → **Import from OpenAPI**\n"
            f"2. Upload `openapi-spec.json`\n"
            f"3. Configure OAuth connection with EXP tenant credentials\n"
            f"4. Test the action with a sample question\n"
        )

    def _full_setup(self, copilot_name, data_agent_name, workspace, channel, auth_type, description, topics):
        sections = [
            f"# Full Copilot Studio Setup: `{copilot_name}`\n",
            f"**Data Agent:** {data_agent_name}\n",
            f"**Workspace:** {workspace}\n",
            f"**Channel:** {CHANNELS.get(channel, {}).get('display', channel)}\n\n---\n",
            self._create_copilot(copilot_name, description, workspace),
            "\n---\n",
            self._configure_auth(copilot_name, auth_type, workspace),
            "\n---\n",
            self._add_data_agent_plugin(copilot_name, data_agent_name, workspace),
            "\n---\n",
            self._add_channel(copilot_name, channel),
            "\n---\n",
            self._create_declarative_agent(copilot_name, data_agent_name, workspace, description, topics),
            "\n---\n",
            "## End-to-End Flow\n\n"
            "```\n"
            f"[User in {CHANNELS.get(channel, {}).get('display', channel)}]\n"
            f"  → \"{copilot_name}, what were sales last quarter?\"\n"
            f"       │\n"
            f"       ▼\n"
            f"[Copilot Studio: {copilot_name}]\n"
            f"  → Recognizes data query intent\n"
            f"  → Calls Fabric Data Agent plugin\n"
            f"       │\n"
            f"       ▼\n"
            f"[Fabric Data Agent: {data_agent_name}]\n"
            f"  → Generates SQL: SELECT SUM(amount) FROM fact_sales WHERE ...\n"
            f"  → Executes against Lakehouse SQL endpoint\n"
            f"  → Returns results\n"
            f"       │\n"
            f"       ▼\n"
            f"[Copilot Studio: {copilot_name}]\n"
            f"  → Formats response with adaptive card\n"
            f"  → Returns to user\n"
            "```\n",
        ]
        return "\n".join(sections)

    def _best_practices(self):
        lines = ["# Copilot Studio — Best Practices\n"]
        lines.append("*Source: Microsoft Learn documentation (2025)*\n")
        for category, practices in BEST_PRACTICES.items():
            lines.append(f"\n## {category.replace('_', ' ').title()}\n")
            for p in practices:
                lines.append(f"- {p}")
        lines.append("\n\n## Security Defaults (DO NOT DISABLE)\n")
        lines.append("- ✅ Authenticate with Microsoft (Entra ID)")
        lines.append("- ✅ End-user credentials for connectors")
        lines.append("- ✅ Security scan before publishing")
        lines.append("- ✅ DLP policies enforced on knowledge sources")
        lines.append("- ✅ Sensitivity labels on responses")
        lines.append(f"\n📖 Docs: https://learn.microsoft.com/microsoft-copilot-studio/security-overview")
        return "\n".join(lines)
