"""
Semantic Model Agent — creates Power BI semantic models (Direct Lake or Import)
over Fabric Lakehouse/Warehouse data, defines measures and relationships,
and generates Power BI report scaffolds (.pbip format).

Responsibilities:
  1. Create Direct Lake semantic models over Lakehouse/Warehouse
  2. Define DAX measures (KPIs, time-intelligence, aggregations)
  3. Configure relationships between tables
  4. Generate Power BI report projects (.pbip) with recommended visuals
  5. Deploy to Fabric workspace

Drop this file into any brainstem agents/ directory. No external deps beyond requests.
"""

import json
from agents.basic_agent import BasicAgent
from agents.auth_config import TARGET_M365_TENANT, SCOPES, get_fabric_auth_preamble


# ── Common DAX patterns ────────────────────────────────────────────────────

DAX_PATTERNS = {
    "total_sales": {
        "name": "Total Sales",
        "expression": "SUM('{table}'[{amount_col}])",
        "format": "$#,##0.00",
    },
    "ytd": {
        "name": "{measure_name} YTD",
        "expression": "TOTALYTD([{base_measure}], '{date_table}'[{date_col}])",
        "format": "$#,##0.00",
    },
    "mom_growth": {
        "name": "MoM Growth %",
        "expression": (
            "VAR CurrentMonth = [Total Sales]\n"
            "VAR PreviousMonth = CALCULATE([Total Sales], DATEADD('{date_table}'[{date_col}], -1, MONTH))\n"
            "RETURN DIVIDE(CurrentMonth - PreviousMonth, PreviousMonth)"
        ),
        "format": "0.00%",
    },
    "running_total": {
        "name": "Running Total",
        "expression": (
            "CALCULATE([{base_measure}], "
            "FILTER(ALL('{date_table}'[{date_col}]), '{date_table}'[{date_col}] <= MAX('{date_table}'[{date_col}])))"
        ),
        "format": "$#,##0.00",
    },
    "count_distinct": {
        "name": "Distinct {col} Count",
        "expression": "DISTINCTCOUNT('{table}'[{col}])",
        "format": "#,##0",
    },
    "average": {
        "name": "Average {col}",
        "expression": "AVERAGE('{table}'[{col}])",
        "format": "#,##0.00",
    },
}

# ── Relationship types ─────────────────────────────────────────────────────

CARDINALITIES = ["OneToMany", "ManyToOne", "OneToOne", "ManyToMany"]
CROSS_FILTER_DIRECTIONS = ["Single", "Both", "Automatic"]

# ── Visual recommendations by data type ────────────────────────────────────

VISUAL_RECOMMENDATIONS = {
    "time_series": ["lineChart", "areaChart", "columnChart"],
    "comparison": ["clusteredBarChart", "clusteredColumnChart", "waterfallChart"],
    "composition": ["pieChart", "donutChart", "treemap", "stackedBarChart"],
    "distribution": ["scatterChart", "histogram"],
    "kpi": ["card", "multiRowCard", "gauge"],
    "geographic": ["map", "filledMap", "shapeMap"],
    "tabular": ["table", "matrix"],
}

# ── Microsoft Best Practices for Direct Lake / Semantic Models ─────────────

BEST_PRACTICES = {
    "direct_lake_optimization": [
        "Target 1M to 16M rows per row group for optimal column segment performance",
        "Avoid destructive Delta operations (VACUUM with low retention, OPTIMIZE with ZORDER on high-cardinality cols) that break framing",
        "Avoid high-cardinality partition columns — partitions become row groups",
        "Use V-Order optimization on Delta tables for best Direct Lake scan performance",
        "Do NOT use calculated columns or calculated tables that reference Direct Lake columns",
        "Monitor DirectQuery fallback with Performance Analyzer — fallback degrades performance significantly",
        "Enable XMLA endpoint (Read/Write) for Direct Lake models created in Desktop",
    ],
    "data_types_and_columns": [
        "String columns limited to 32,764 characters — longer values truncated",
        "NaN values NOT supported — replace with NULL before loading",
        "Unsupported Delta types: binary, GUID/UUID — convert to string",
        "Match relationship column data types exactly (Int64 to Int64, not Int64 to String)",
        "Unique values required on the 'one' side of relationships",
        "Date tables must be marked as Date Table and have no gaps",
    ],
    "dax_measures": [
        "Define measures in a dedicated '_Measures' table for discoverability",
        "Use DIVIDE() instead of / to handle divide-by-zero gracefully",
        "Use CALCULATE + FILTER instead of nested IF for complex conditions",
        "Use time-intelligence functions (TOTALYTD, SAMEPERIODLASTYEAR) with a proper Date table",
        "Format strings should match the business context (currency, %, integer)",
        "Document measure descriptions for self-service users",
    ],
    "relationships": [
        "Prefer star schema — facts reference dimensions via surrogate keys",
        "One active relationship per path between tables (use USERELATIONSHIP for alternates)",
        "Many-to-many relationships require careful bidirectional filtering — minimize their use",
        "Cross-filter direction 'Both' increases model complexity — use 'Single' unless required",
        "Relationship columns should NOT contain NULLs — blank keys won't match",
    ],
    "security_and_governance": [
        "Use row-level security (RLS) for multi-tenant data access control",
        "Apply object-level security (OLS) to hide sensitive columns from roles",
        "Use deployment pipelines for DEV → TEST → PROD promotion",
        "Configure incremental refresh if using Import mode tables alongside Direct Lake",
        "Workspace roles (Viewer/Contributor/Admin) control model access — follow least privilege",
    ],
    "performance": [
        "Reduce model size: remove unused columns and tables",
        "Prefer measures over calculated columns for dynamic computations",
        "Avoid bidirectional cross-filtering unless absolutely necessary",
        "Use aggregation tables for large fact tables with summarized pre-calculations",
        "Monitor query performance with DAX Studio and Performance Analyzer",
        "Set 'Default Summarization' to 'Do Not Summarize' for non-additive columns",
    ],
}


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/semantic-model",
    "version": "1.0.0",
    "display_name": "Semantic Model Agent",
    "description": (
        "Create Power BI semantic models (Direct Lake) over Fabric Lakehouse or "
        "Warehouse, define DAX measures and relationships, generate report scaffolds."
    ),
    "author": "Kody",
    "tags": ["fabric", "power-bi", "semantic-model", "direct-lake", "dax", "report"],
    "category": "analytics",
    "quality_tier": "community",
    "dependencies": ["@rapp/basic_agent"],
}


class SemanticModelAgent(BasicAgent):
    """Creates semantic models and Power BI reports in Fabric."""

    def __init__(self):
        self.name = "semantic_model"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "create_model", "add_measures", "add_relationships",
                            "generate_report", "deploy", "recommend_visuals", "full_setup",
                            "best_practices",
                        ],
                        "description": "Action to perform",
                    },
                    "workspace": {
                        "type": "string",
                        "description": "Fabric workspace name",
                    },
                    "model_name": {
                        "type": "string",
                        "description": "Semantic model name",
                    },
                    "lakehouse_name": {
                        "type": "string",
                        "description": "Source Lakehouse or Warehouse name",
                    },
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tables to include in the model",
                    },
                    "measures": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "expression": {"type": "string"},
                                "table": {"type": "string"},
                                "format": {"type": "string"},
                            },
                        },
                        "description": "DAX measures to create",
                    },
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from_table": {"type": "string"},
                                "from_column": {"type": "string"},
                                "to_table": {"type": "string"},
                                "to_column": {"type": "string"},
                                "cardinality": {"type": "string"},
                            },
                        },
                        "description": "Relationships between tables",
                    },
                    "report_name": {
                        "type": "string",
                        "description": "Power BI report name",
                    },
                    "data_category": {
                        "type": "string",
                        "enum": list(VISUAL_RECOMMENDATIONS.keys()),
                        "description": "Primary data category for visual recommendations",
                    },
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        action = kwargs.get("action", "create_model")
        workspace = kwargs.get("workspace", "demo-workspace")
        model_name = kwargs.get("model_name", "semantic-model-demo")
        lakehouse_name = kwargs.get("lakehouse_name", "lakehouse-bronze")
        tables = kwargs.get("tables", ["fact_sales", "dim_customer", "dim_product", "dim_date"])
        measures = kwargs.get("measures", [])
        relationships = kwargs.get("relationships", [])
        report_name = kwargs.get("report_name", f"report-{model_name}")
        data_category = kwargs.get("data_category", "time_series")

        handlers = {
            "create_model": lambda: self._create_model(workspace, model_name, lakehouse_name, tables),
            "add_measures": lambda: self._add_measures(workspace, model_name, tables, measures),
            "add_relationships": lambda: self._add_relationships(workspace, model_name, relationships, tables),
            "generate_report": lambda: self._generate_report(workspace, model_name, report_name, tables, data_category),
            "deploy": lambda: self._deploy(workspace, model_name),
            "recommend_visuals": lambda: self._recommend_visuals(data_category, tables),
            "full_setup": lambda: self._full_setup(
                workspace, model_name, lakehouse_name, tables, measures, relationships, report_name
            ),
            "best_practices": lambda: self._best_practices(),
        }

        handler = handlers.get(action)
        if handler:
            return handler()
        return f"Unknown action: {action}"

    # ── Handlers ───────────────────────────────────────────────────────────

    def _create_model(self, workspace, model_name, lakehouse_name, tables):
        auth = get_fabric_auth_preamble(workspace)
        table_defs = json.dumps([{"name": t, "sourceLineageTag": f"[dbo].[{t}]"} for t in tables], indent=4)

        script = (
            f'"""\n'
            f'Create Direct Lake Semantic Model: {model_name}\n'
            f'Source: Lakehouse "{lakehouse_name}" (SQL Analytics Endpoint)\n'
            f'Tables: {", ".join(tables)}\n'
            f'"""\n\n'
            f'{auth}\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# Direct Lake connects to the SQL Analytics Endpoint of a Lakehouse\n'
            f'# No data import needed — queries go directly to Delta Parquet in OneLake\n\n'
            f'payload = {{\n'
            f'    "displayName": "{model_name}",\n'
            f'    "type": "SemanticModel",\n'
            f'    "definition": {{\n'
            f'        "parts": [{{\n'
            f'            "path": "model.bim",\n'
            f'            "payload": {{\n'
            f'                "model": {{\n'
            f'                    "defaultMode": "DirectLake",\n'
            f'                    "tables": {table_defs},\n'
            f'                    "expressions": [{{\n'
            f'                        "name": "DatabaseQuery",\n'
            f'                        "kind": "m",\n'
            f'                        "expression": "let Source = Sql.Database(\\"{lakehouse_name}-sql\\", \\"{lakehouse_name}\\") in Source"\n'
            f'                    }}]\n'
            f'                }}\n'
            f'            }}\n'
            f'        }}]\n'
            f'    }}\n'
            f'}}\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/semanticModels",\n'
            f'    headers=headers,\n'
            f'    json=payload\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'model = resp.json()\n'
            f'print(f"Semantic model created: {{model[\'id\']}}")\n'
            f'print(f"Mode: Direct Lake (zero-copy from OneLake)")\n'
        )

        return (
            f"## Create Direct Lake Semantic Model: `{model_name}`\n\n"
            f"**Source:** {lakehouse_name} (SQL Analytics Endpoint)\n"
            f"**Tables:** {', '.join(tables)}\n"
            f"**Mode:** Direct Lake (queries read directly from OneLake — no import)\n\n"
            f"```python\n{script}\n```\n\n"
            f"### Direct Lake Benefits\n"
            f"- No data duplication (queries read Delta Parquet directly)\n"
            f"- Automatic refresh when Lakehouse data changes\n"
            f"- Performance of Import mode with freshness of DirectQuery\n"
        )

    def _add_measures(self, workspace, model_name, tables, measures):
        if not measures:
            # Generate default measures based on common patterns
            fact_table = tables[0] if tables else "fact_sales"
            date_table = next((t for t in tables if "date" in t.lower()), "dim_date")
            measures = [
                {"name": "Total Sales", "expression": f"SUM('{fact_table}'[Amount])", "table": fact_table, "format": "$#,##0.00"},
                {"name": "Order Count", "expression": f"COUNTROWS('{fact_table}')", "table": fact_table, "format": "#,##0"},
                {"name": "Average Order Value", "expression": f"DIVIDE([Total Sales], [Order Count])", "table": fact_table, "format": "$#,##0.00"},
                {"name": "Sales YTD", "expression": f"TOTALYTD([Total Sales], '{date_table}'[Date])", "table": fact_table, "format": "$#,##0.00"},
                {"name": "Sales MoM %", "expression": f"VAR Curr = [Total Sales]\nVAR Prev = CALCULATE([Total Sales], DATEADD('{date_table}'[Date], -1, MONTH))\nRETURN DIVIDE(Curr - Prev, Prev)", "table": fact_table, "format": "0.0%"},
            ]

        lines = [f"## DAX Measures for `{model_name}`\n"]
        lines.append("Add these measures via XMLA endpoint or Tabular Editor:\n")
        lines.append("```dax")
        for m in measures:
            lines.append(f"-- Measure: {m['name']} (Table: {m.get('table', tables[0])})")
            lines.append(f"{m['name']} = {m['expression']}")
            lines.append("")
        lines.append("```\n")

        # Also provide the TMSL script
        lines.append("### TMSL (Tabular Model Scripting Language)\n")
        lines.append("```json")
        tmsl = {
            "createOrReplace": {
                "object": {"database": model_name},
                "measures": [
                    {
                        "name": m["name"],
                        "expression": m["expression"],
                        "formatString": m.get("format", ""),
                    }
                    for m in measures
                ],
            }
        }
        lines.append(json.dumps(tmsl, indent=2))
        lines.append("```\n")

        lines.append("### Available DAX Patterns\n")
        for key, pattern in DAX_PATTERNS.items():
            lines.append(f"- `{key}`: {pattern['name']}")

        return "\n".join(lines)

    def _add_relationships(self, workspace, model_name, relationships, tables):
        if not relationships:
            # Infer star-schema relationships
            fact_table = next((t for t in tables if "fact" in t.lower()), tables[0])
            dim_tables = [t for t in tables if t != fact_table]
            relationships = []
            for dim in dim_tables:
                # Guess the key column
                dim_short = dim.replace("dim_", "").replace("Dim", "")
                relationships.append({
                    "from_table": fact_table,
                    "from_column": f"{dim_short}_id",
                    "to_table": dim,
                    "to_column": f"{dim_short}_id",
                    "cardinality": "ManyToOne",
                })

        lines = [f"## Relationships for `{model_name}`\n"]
        lines.append("| From | Column | → | To | Column | Cardinality |")
        lines.append("|------|--------|---|-----|--------|-------------|")
        for r in relationships:
            lines.append(
                f"| {r['from_table']} | {r['from_column']} | → | "
                f"{r['to_table']} | {r['to_column']} | {r.get('cardinality', 'ManyToOne')} |"
            )
        lines.append("")

        # TMSL for relationships
        lines.append("### TMSL Script\n```json")
        tmsl_rels = []
        for r in relationships:
            tmsl_rels.append({
                "name": f"{r['from_table']}_{r['to_table']}",
                "fromTable": r["from_table"],
                "fromColumn": r["from_column"],
                "toTable": r["to_table"],
                "toColumn": r["to_column"],
                "fromCardinality": r.get("cardinality", "ManyToOne").split("To")[0].lower(),
                "toCardinality": r.get("cardinality", "ManyToOne").split("To")[1].lower() if "To" in r.get("cardinality", "") else "one",
                "crossFilteringBehavior": "singleDirection",
            })
        lines.append(json.dumps({"relationships": tmsl_rels}, indent=2))
        lines.append("```\n")

        return "\n".join(lines)

    def _generate_report(self, workspace, model_name, report_name, tables, data_category):
        auth = get_fabric_auth_preamble(workspace)
        visuals = VISUAL_RECOMMENDATIONS.get(data_category, VISUAL_RECOMMENDATIONS["time_series"])

        script = (
            f'{auth}\n'
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# Create a Power BI report connected to the semantic model\n'
            f'# Option 1: Via API\n'
            f'payload = {{\n'
            f'    "displayName": "{report_name}",\n'
            f'    "type": "Report",\n'
            f'    "definition": {{\n'
            f'        "parts": [{{\n'
            f'            "path": "report.json",\n'
            f'            "payload": {{\n'
            f'                "datasetId": "<semantic-model-id>"\n'
            f'            }}\n'
            f'        }}]\n'
            f'    }}\n'
            f'}}\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/reports",\n'
            f'    headers=headers,\n'
            f'    json=payload\n'
            f')\n'
            f'resp.raise_for_status()\n'
            f'report = resp.json()\n'
            f'print(f"Report created: {{report[\'id\']}}")\n'
        )

        return (
            f"## Generate Report: `{report_name}`\n\n"
            f"**Semantic Model:** {model_name}\n"
            f"**Data Category:** {data_category}\n\n"
            f"```python\n{script}\n```\n\n"
            f"### Recommended Visuals for `{data_category}` data\n\n"
            + "\n".join(f"- {v}" for v in visuals) + "\n\n"
            f"### Suggested Report Layout\n\n"
            f"| Page | Purpose | Visuals |\n"
            f"|------|---------|----------|\n"
            f"| Overview | KPIs at a glance | Card, Gauge, Multi-row card |\n"
            f"| Trends | Time-based analysis | Line chart, Area chart |\n"
            f"| Details | Drill-down | Matrix, Table with conditional formatting |\n"
            f"| Comparison | Segment analysis | Clustered bar, Waterfall |\n"
        )

    def _deploy(self, workspace, model_name):
        auth = get_fabric_auth_preamble(workspace)
        return (
            f"## Deploy Semantic Model: `{model_name}`\n\n"
            f"```python\n{auth}\n"
            f'FABRIC_API = "https://api.fabric.microsoft.com/v1"\n\n'
            f'# Trigger a refresh (Direct Lake models auto-refresh, but you can force it)\n'
            f'model_id = "<semantic-model-id>"\n\n'
            f'resp = requests.post(\n'
            f'    f"{{FABRIC_API}}/workspaces/{{workspace_id}}/semanticModels/{{model_id}}/refresh",\n'
            f'    headers=headers,\n'
            f'    json={{"type": "Full"}}\n'
            f')\n'
            f'if resp.status_code == 202:\n'
            f'    print("Refresh initiated")\n'
            f'else:\n'
            f'    print(f"Status: {{resp.status_code}} — {{resp.text}}")\n'
            f'```\n\n'
            f"### Deployment Checklist\n"
            f"- [ ] Semantic model created with all tables\n"
            f"- [ ] Relationships configured (star schema)\n"
            f"- [ ] DAX measures added\n"
            f"- [ ] Report pages built\n"
            f"- [ ] Row-Level Security (RLS) configured if needed\n"
            f"- [ ] Workspace roles assigned for consumers\n"
        )

    def _recommend_visuals(self, data_category, tables):
        visuals = VISUAL_RECOMMENDATIONS.get(data_category, [])
        lines = [f"## Visual Recommendations: `{data_category}`\n"]
        lines.append("### Primary Visuals")
        for v in visuals:
            lines.append(f"- **{v}**")
        lines.append("\n### All Categories\n")
        for cat, vis_list in VISUAL_RECOMMENDATIONS.items():
            lines.append(f"**{cat}:** {', '.join(vis_list)}")
        return "\n".join(lines)

    def _full_setup(self, workspace, model_name, lakehouse_name, tables, measures, relationships, report_name):
        sections = [
            f"# Full Semantic Model Setup: `{model_name}`\n",
            f"**Workspace:** {workspace}\n",
            f"**Source:** {lakehouse_name}\n\n---\n",
            self._create_model(workspace, model_name, lakehouse_name, tables),
            "\n---\n",
            self._add_relationships(workspace, model_name, relationships, tables),
            "\n---\n",
            self._add_measures(workspace, model_name, tables, measures),
            "\n---\n",
            self._generate_report(workspace, model_name, report_name, tables, "time_series"),
            "\n---\n",
            self._deploy(workspace, model_name),
        ]
        return "\n".join(sections)

    def _best_practices(self):
        lines = ["# Semantic Model (Direct Lake) — Best Practices\n"]
        lines.append("*Source: Microsoft Learn documentation (2025)*\n")
        for category, practices in BEST_PRACTICES.items():
            lines.append(f"\n## {category.replace('_', ' ').title()}\n")
            for p in practices:
                lines.append(f"- {p}")
        lines.append("\n\n## Quick Validation Checklist\n")
        lines.append("- [ ] Row groups between 1M–16M rows")
        lines.append("- [ ] No calculated columns referencing Direct Lake tables")
        lines.append("- [ ] Relationship columns have matching data types")
        lines.append("- [ ] One-side columns have unique values (no duplicates)")
        lines.append("- [ ] No NaN values in any column")
        lines.append("- [ ] String columns under 32,764 characters")
        lines.append("- [ ] XMLA endpoint enabled (Read/Write)")
        lines.append("- [ ] Star schema design (facts → dimensions)")
        lines.append("- [ ] Performance Analyzer shows no unexpected DirectQuery fallback")
        lines.append(f"\n📖 Docs: https://learn.microsoft.com/fabric/fundamentals/direct-lake-overview")
        return "\n".join(lines)
