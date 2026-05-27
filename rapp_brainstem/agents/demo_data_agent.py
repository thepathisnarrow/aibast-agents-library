"""
Demo Data Agent — sources realistic demo data for a customer scenario.

Strategy:
  1. If a customer website URL is provided, attempt a best-effort fetch of
     publicly-available structured information (product catalog, locations,
     press releases, SEC filings landing pages, etc.) and synthesize a
     small dataset shape from it.
  2. If no public data can be pulled (or no URL given), generate an
     industry-appropriate synthetic dataset based on `industry_primary`
     (and `industry_secondary` if provided).

This agent never *provisions* anything — it returns a dataset plan (table
schemas + sample rows + suggested file layout) for the `data_engineer`
builder agent to land in Fabric.

Network access for the public-data fetch is best-effort. If `requests` is
unavailable or the fetch fails, the agent silently falls back to synthetic
data and logs the reason.
"""

import json
from agents.basic_agent import BasicAgent


# ── Industry → synthetic dataset templates ─────────────────────────────────

INDUSTRY_DATASETS = {
    "Retail & Consumer Goods": {
        "tables": [
            ("dim_product", ["product_id", "sku", "name", "category", "brand", "unit_price"]),
            ("dim_store", ["store_id", "name", "region", "city", "state", "open_date"]),
            ("dim_customer", ["customer_id", "first_name", "last_name", "email", "loyalty_tier"]),
            ("fact_sales", ["sale_id", "ts", "store_id", "product_id", "customer_id", "qty", "amount"]),
            ("fact_inventory", ["ts", "store_id", "product_id", "on_hand", "reorder_point"]),
        ],
        "sample_volumes": "dim ~100 rows; fact_sales ~50k; fact_inventory ~10k",
        "themes": ["seasonality", "stockouts", "loyalty-tier upsell"],
    },
    "Healthcare": {
        "tables": [
            ("dim_patient", ["patient_id", "mrn_hash", "age_band", "sex", "zip3"]),
            ("dim_provider", ["provider_id", "name", "specialty", "facility_id"]),
            ("fact_encounter", ["encounter_id", "patient_id", "provider_id", "ts", "encounter_type", "diagnosis_code", "los_hours"]),
            ("fact_readmission", ["patient_id", "index_ts", "readmit_within_30d"]),
        ],
        "sample_volumes": "dim ~500 rows; fact_encounter ~20k; fact_readmission ~5k",
        "themes": ["30-day readmission risk", "wait-time hotspots", "no-show rates"],
    },
    "Financial Services": {
        "tables": [
            ("dim_account", ["account_id", "customer_id", "account_type", "open_date", "tier"]),
            ("dim_customer", ["customer_id", "age_band", "segment", "kyc_status"]),
            ("fact_transaction", ["txn_id", "ts", "account_id", "amount", "merchant_category", "fraud_score"]),
            ("fact_position", ["snapshot_date", "account_id", "asset_class", "market_value"]),
        ],
        "sample_volumes": "dim ~1k rows; fact_transaction ~100k; fact_position ~30k",
        "themes": ["fraud signal", "AUM trend", "AML alerts"],
    },
    "Industrials & Manufacturing": {
        "tables": [
            ("dim_asset", ["asset_id", "line_id", "type", "install_date", "model"]),
            ("dim_line", ["line_id", "facility", "shift"]),
            ("fact_telemetry", ["ts", "asset_id", "temperature_c", "vibration_g", "rpm"]),
            ("fact_downtime", ["asset_id", "start_ts", "end_ts", "reason_code"]),
        ],
        "sample_volumes": "dim ~50 rows; fact_telemetry ~500k (streaming); fact_downtime ~200",
        "themes": ["OEE", "predictive failure", "shift performance"],
    },
    "Energy & Resources": {
        "tables": [
            ("dim_meter", ["meter_id", "site_id", "type", "install_date"]),
            ("dim_site", ["site_id", "name", "region", "latitude", "longitude"]),
            ("fact_reading", ["ts", "meter_id", "kwh", "voltage", "anomaly_flag"]),
        ],
        "sample_volumes": "fact_reading ~1M (streaming)",
        "themes": ["peak load", "anomaly detection", "carbon intensity"],
    },
    "Government": {
        "tables": [
            ("dim_case", ["case_id", "agency_id", "type", "opened_at", "status"]),
            ("dim_agency", ["agency_id", "name", "jurisdiction"]),
            ("fact_case_activity", ["case_id", "ts", "actor", "action", "outcome"]),
        ],
        "sample_volumes": "fact_case_activity ~30k",
        "themes": ["case aging", "backlog", "SLA adherence"],
    },
    "Education": {
        "tables": [
            ("dim_student", ["student_id", "grade", "cohort", "program"]),
            ("dim_course", ["course_id", "subject", "instructor_id"]),
            ("fact_assessment", ["student_id", "course_id", "term", "score", "submitted_at"]),
            ("fact_attendance", ["student_id", "date", "present"]),
        ],
        "sample_volumes": "fact_assessment ~20k; fact_attendance ~80k",
        "themes": ["at-risk early warning", "term-over-term improvement"],
    },
    "Telecommunications & Media": {
        "tables": [
            ("dim_subscriber", ["subscriber_id", "plan", "tenure_months", "region"]),
            ("fact_cdr", ["ts", "subscriber_id", "duration_sec", "destination", "drop_flag"]),
            ("fact_churn", ["subscriber_id", "snapshot_date", "churned_30d"]),
        ],
        "sample_volumes": "fact_cdr ~200k; fact_churn ~5k",
        "themes": ["network quality", "churn risk", "ARPU"],
    },
    "Travel Transportation & Hospitality": {
        "tables": [
            ("dim_property", ["property_id", "city", "country", "rooms"]),
            ("dim_guest", ["guest_id", "loyalty_tier", "country"]),
            ("fact_booking", ["booking_id", "ts", "property_id", "guest_id", "nights", "revenue"]),
            ("fact_occupancy", ["property_id", "date", "occupancy_pct", "adr"]),
        ],
        "sample_volumes": "fact_booking ~30k; fact_occupancy ~10k",
        "themes": ["RevPAR", "seasonality", "loyalty conversion"],
    },
    "Automotive Mobility & Transportation": {
        "tables": [
            ("dim_vehicle", ["vehicle_id", "model", "year", "fleet_id"]),
            ("fact_trip", ["trip_id", "vehicle_id", "start_ts", "end_ts", "distance_km", "energy_kwh"]),
            ("fact_diagnostic", ["vehicle_id", "ts", "dtc_code", "severity"]),
        ],
        "sample_volumes": "fact_trip ~50k; fact_diagnostic ~10k",
        "themes": ["fleet utilization", "predictive maintenance", "range/efficiency"],
    },
    "Professional Services": {
        "tables": [
            ("dim_consultant", ["consultant_id", "level", "practice"]),
            ("dim_engagement", ["engagement_id", "client_id", "type", "start_date"]),
            ("fact_timesheet", ["consultant_id", "engagement_id", "date", "hours", "billable"]),
        ],
        "sample_volumes": "fact_timesheet ~40k",
        "themes": ["utilization", "realization rate", "engagement margin"],
    },
    "Sustainability": {
        "tables": [
            ("dim_facility", ["facility_id", "country", "type"]),
            ("dim_supplier", ["supplier_id", "tier", "country"]),
            ("fact_emissions", ["facility_id", "month", "scope_1", "scope_2", "scope_3"]),
            ("fact_waste", ["facility_id", "month", "kg_landfill", "kg_recycled"]),
        ],
        "sample_volumes": "fact_emissions ~12*N; fact_waste ~12*N",
        "themes": ["scope 1/2/3 trend", "supplier risk", "diversion rate"],
    },
    "Defense & Intelligence": {
        "tables": [
            ("dim_mission", ["mission_id", "type", "unit_id"]),
            ("dim_asset", ["asset_id", "platform", "status"]),
            ("fact_event", ["ts", "mission_id", "asset_id", "event_type", "geo"]),
        ],
        "sample_volumes": "fact_event ~10k (synthetic, unclassified)",
        "themes": ["operational readiness", "logistics", "sensor fusion"],
        "warning": "Use ONLY synthetic / unclassified data. Never real operational data.",
    },
}


__manifest__ = {
    "schema": "rapp-agent/1.0",
    "name": "@kody/demo-data",
    "version": "1.0.0",
    "display_name": "Demo Data Agent",
    "description": (
        "Sources demo data: best-effort pull of public information from a "
        "customer website, with synthetic industry-appropriate fallback."
    ),
    "tags": ["data", "synthetic", "industry", "scraping"],
    "category": "data",
}


class DemoDataAgent(BasicAgent):
    """Sources realistic demo data — public first, synthetic fallback."""

    def __init__(self):
        self.name = "demo_data"
        self.metadata = {
            "name": self.name,
            "description": __manifest__["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["source"],
                        "description": "source = produce a dataset plan.",
                    },
                    "customer_website_url": {
                        "type": "string",
                        "description": "Customer website (optional). Best-effort fetch.",
                    },
                    "industry_primary": {
                        "type": "string",
                        "description": "Primary industry (required for synthetic fallback).",
                    },
                    "industry_secondary": {
                        "type": "string",
                        "description": "Secondary industry (optional).",
                    },
                    "customer_name": {"type": "string"},
                },
                "required": ["action"],
            },
        }
        super().__init__()

    def perform(self, **kwargs):
        if kwargs.get("action") != "source":
            return f"Unknown action: {kwargs.get('action')}"
        return self._source(
            kwargs.get("customer_website_url") or "",
            kwargs.get("industry_primary") or "",
            kwargs.get("industry_secondary") or "",
            kwargs.get("customer_name") or "Customer",
        )

    def _source(self, url: str, ind: str, ind2: str, customer: str) -> str:
        public = self._try_public_fetch(url) if url else None

        primary_template = INDUSTRY_DATASETS.get(ind) or self._generic()
        secondary_template = INDUSTRY_DATASETS.get(ind2) if ind2 else None

        lines = [
            f"# Demo Data Plan — {customer}",
            "",
            f"**Customer website:** {url or '(none provided)'}",
            f"**Industry:** {ind or '(unspecified)'}" + (f" / {ind2}" if ind2 else ""),
            "",
        ]

        if public:
            lines += [
                "## Public Data — Fetched",
                f"Pulled the following from `{url}`:",
                "",
                "```",
                public[:2000],
                "```" if len(public) <= 2000 else "...(truncated)\n```",
                "",
                "**Recommendation:** seed the demo narrative with these real facts "
                "(brand voice, product names, geographies). Combine with the synthetic "
                "tables below for transactional volumes.",
                "",
            ]
        elif url:
            lines += [
                "## Public Data — Not Available",
                f"Attempted to fetch `{url}` but no usable structured data returned. "
                "Falling back to synthetic data based on industry.",
                "",
            ]
        else:
            lines += [
                "## Public Data — Skipped",
                "No customer website URL was provided. Using synthetic data only.",
                "",
            ]

        lines += [
            "## Synthetic Dataset (Industry-Appropriate)",
            f"**Industry template:** {ind or 'generic'}",
            f"**Sample volumes:** {primary_template.get('sample_volumes', 'small')}",
            f"**Narrative themes:** {', '.join(primary_template.get('themes', []))}",
        ]
        if primary_template.get("warning"):
            lines.append(f"\n> ⚠ {primary_template['warning']}")
        lines += ["", "### Tables", "| Table | Columns |", "|-------|---------|"]
        for tname, cols in primary_template["tables"]:
            lines.append(f"| `{tname}` | {', '.join(cols)} |")

        if secondary_template:
            lines += [
                "",
                f"### Cross-industry overlay — {ind2}",
            ]
            for tname, cols in secondary_template["tables"][:2]:
                lines.append(f"- Add `{tname}` ({', '.join(cols)}) for narrative depth.")

        lines += [
            "",
            "## File Layout (for `data_engineer` to land)",
            "```",
            "  /bronze/  → CSV exactly as generated",
            "  /silver/  → Delta, deduped & typed",
            "  /gold/    → Delta, joined star schema",
            "```",
            "",
            "## Hand-off",
            "Call `data_engineer` with these table specs to land them in the bronze lakehouse, "
            "then run the bronze→silver→gold notebook.",
            "",
            "```json",
            json.dumps({
                "industry_primary": ind,
                "industry_secondary": ind2,
                "tables": [{"name": t, "columns": c} for t, c in primary_template["tables"]],
            }, indent=2),
            "```",
        ]
        return "\n".join(lines)

    def _try_public_fetch(self, url: str) -> str | None:
        """Best-effort fetch of a customer website. Returns plain-text excerpt
        or None on any failure."""
        try:
            import requests
        except ImportError:
            return None
        try:
            r = requests.get(
                url,
                timeout=8,
                headers={"User-Agent": "Brainstem Demo Data Agent (best-effort fetch)"},
            )
            if r.status_code != 200:
                return None
            text = r.text
            # crude HTML→text: strip tags
            import re
            text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:3000] or None
        except Exception:
            return None

    def _generic(self) -> dict:
        return {
            "tables": [
                ("dim_entity", ["entity_id", "name", "type", "region"]),
                ("fact_event", ["ts", "entity_id", "metric_name", "metric_value"]),
            ],
            "sample_volumes": "dim ~100 rows; fact_event ~20k",
            "themes": ["trend over time", "outlier detection"],
        }
