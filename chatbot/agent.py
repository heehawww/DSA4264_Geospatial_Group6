from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from .api_client import HDBApiClient


DEFAULT_AGENT_MODEL = "openai:gpt-4.1-mini"

AGENT_INSTRUCTIONS = """
You are an HDB resale assistant for non-technical stakeholders. Answer from
the current map context and the FastAPI tools. Explain prices, towns, primary school
access, and what-if estimates in plain language. Avoid technical statistics
terms unless the user explicitly asks for them.

When describing model outputs, say "estimate", "pattern", "comparison", or
"suggests" instead of statistical jargon. Do not mention coefficients,
regression, RDD, p-values, bandwidths, specifications, or causal effects unless
the user explicitly asks for methodology. If the evidence is limited, say that
plainly, for example: "This is an estimate, not a guarantee."

Do not apply the Streamlit map filters to API tools unless the user explicitly
asks about the current map selection. Treat user-provided constraints such as
town, month, flat type, school exposure, or price range as separate API query
filters.

Return a natural chat response, not a report. Avoid Markdown headings, tables,
code blocks, raw JSON, and bullet lists unless the user explicitly asks for
them. Prefer one short paragraph. If you mention currency, write it as
"SGD 330,000" instead of "S$330,000" so the frontend does not interpret dollar
signs as math markup.
""".strip()


class ChatAnswer(BaseModel):
    answer: str = Field(
        description=(
            "A natural-language chatbot reply for non-technical stakeholders. Use prose, "
            "avoid markdown headings/tables/statistical jargon, and use SGD currency wording "
            "rather than dollar-sign notation."
        )
    )


@dataclass
class HDBAgentDeps:
    api: HDBApiClient
    map_context: str


def normalise_model_name(model_name: str | None = None) -> str:
    configured = (
        model_name
        or os.getenv("PYDANTIC_AI_MODEL")
        or os.getenv("OPENAI_MODEL")
        or DEFAULT_AGENT_MODEL
    )
    if ":" in configured:
        return configured
    return f"openai:{configured}"

def build_hdb_agent(model_name: str | None = None):
    from pydantic_ai import Agent, RunContext

    globals()["RunContext"] = RunContext
    agent = Agent(
        normalise_model_name(model_name),
        output_type=ChatAnswer,
        deps_type=HDBAgentDeps,
        instructions=AGENT_INSTRUCTIONS,
        defer_model_check=True,
        retries=1,
    )

    @agent.tool
    def get_current_map_context(ctx: RunContext[HDBAgentDeps]) -> dict[str, Any]:
        """Return the Streamlit map summary if the user explicitly asks about the current map."""
        return {
            "map_context": ctx.deps.map_context,
        }

    @agent.tool
    def get_api_overview(ctx: RunContext[HDBAgentDeps]) -> dict[str, Any]:
        """Return API metadata and supported resale query schema."""
        return {
            "metadata": ctx.deps.api.get("/metadata"),
            "resales_schema": ctx.deps.api.get("/resales/schema"),
            "predict_schema": ctx.deps.api.get("/predict/schema"),
        }

    @agent.tool
    def query_resales(
        ctx: RunContext[HDBAgentDeps],
        town: list[str] | None = None,
        flat_type: list[str] | None = None,
        flat_model: list[str] | None = None,
        street_name: list[str] | None = None,
        block: list[str] | None = None,
        storey_range: list[str] | None = None,
        month: list[str] | None = None,
        month_from: str | None = None,
        month_to: str | None = None,
        min_floor_area_sqm: float | None = None,
        max_floor_area_sqm: float | None = None,
        min_lease_commence_date: int | None = None,
        max_lease_commence_date: int | None = None,
        min_resale_price: float | None = None,
        max_resale_price: float | None = None,
        group_by: str | None = None,
        include_rows: bool = False,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Return resale summary statistics, and optionally sample rows, using only explicit user filters."""
        params = {
            "town": town,
            "flat_type": flat_type,
            "flat_model": flat_model,
            "street_name": street_name,
            "block": block,
            "storey_range": storey_range,
            "month": month,
            "month_from": month_from,
            "month_to": month_to,
            "min_floor_area_sqm": min_floor_area_sqm,
            "max_floor_area_sqm": max_floor_area_sqm,
            "min_lease_commence_date": min_lease_commence_date,
            "max_lease_commence_date": max_lease_commence_date,
            "min_resale_price": min_resale_price,
            "max_resale_price": max_resale_price,
            "group_by": group_by,
        }
        result = {"summary": ctx.deps.api.get("/resales/summary", params)}
        if include_rows:
            result["rows"] = ctx.deps.api.get(
                "/resales/raw",
                {**params, "limit": max(1, min(limit, 100))},
            )
        return result

    @agent.tool
    def query_town_premiums(
        ctx: RunContext[HDBAgentDeps],
        town: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Return town-level good-school premium summary and matching rows."""
        params = {
            "town": town,
            "limit": max(1, min(limit, 100)),
        }
        return {
            "summary": ctx.deps.api.get("/town-premiums/summary"),
            "rows": ctx.deps.api.get("/town-premiums", params),
        }

    @agent.tool
    def get_good_schools_for_town(
        ctx: RunContext[HDBAgentDeps],
        town: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return good primary schools linked to a town."""
        return ctx.deps.api.get(
            "/schools/good",
            {
                "town": town,
                "limit": max(1, min(limit, 200)),
            },
        )

    @agent.tool
    def query_model_outputs(
        ctx: RunContext[HDBAgentDeps],
        include_metrics: bool = True,
        include_feature_importance: bool = False,
        coefficient_term: str | None = None,
        significant_only: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return model metrics, feature importance, and coefficient information."""
        result: dict[str, Any] = {}
        if include_metrics:
            result["metrics"] = ctx.deps.api.get("/model/metrics")
        if include_feature_importance:
            result["feature_importance"] = ctx.deps.api.get(
                "/model/feature-importance",
                {"limit": max(1, min(limit, 1000))},
            )
        if coefficient_term:
            result["coefficient"] = ctx.deps.api.get(f"/model/coefficients/{coefficient_term}")
        else:
            result["coefficients"] = ctx.deps.api.get(
                "/model/coefficients",
                {
                    "significant_only": significant_only,
                    "limit": max(1, min(limit, 1000)),
                },
            )
        return result

    @agent.tool
    def query_rdd_outputs(
        ctx: RunContext[HDBAgentDeps],
        school_name: str | None = None,
        school_group: str | None = None,
        specification: str | None = None,
        bandwidth_m: int | None = None,
        include_summary: bool = False,
        include_school_index: bool = False,
        include_coefficients: bool = False,
        include_skipped: bool = False,
        reason: str | None = None,
        term: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return school-specific RDD outputs, coverage rows, coefficient tables, or skipped rows."""
        result: dict[str, Any] = {}
        if include_summary:
            result["summary"] = ctx.deps.api.get("/rdd/summary")
        if include_school_index:
            result["schools"] = ctx.deps.api.get("/rdd/schools")
        if include_skipped:
            result["skipped"] = ctx.deps.api.get(
                "/rdd/skipped",
                {
                    "school_name": school_name,
                    "school_group": school_group,
                    "reason": reason,
                    "bandwidth_m": bandwidth_m,
                },
            )
            return result
        if include_coefficients:
            result["coefficients"] = ctx.deps.api.get(
                "/rdd/coefficients",
                {
                    "school_name": school_name,
                    "school_group": school_group,
                    "specification": specification,
                    "bandwidth_m": bandwidth_m,
                    "term": term,
                    "limit": max(1, min(limit, 5000)),
                },
            )
            return result
        if school_name:
            result["results"] = ctx.deps.api.get(
                f"/rdd/results/{school_name}",
                {
                    "specification": specification,
                    "bandwidth_m": bandwidth_m,
                },
            )
            return result
        result["results"] = ctx.deps.api.get(
            "/rdd/results",
            {
                "school_name": school_name,
                "school_group": school_group,
                "specification": specification,
                "bandwidth_m": bandwidth_m,
                "limit": max(1, min(limit, 5000)),
            },
        )
        return result

    @agent.tool
    def query_rdd_group_comparison(
        ctx: RunContext[HDBAgentDeps],
        specification: str | None = None,
        bandwidth_m: int | None = None,
        include_coefficients: bool = False,
        term: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return pooled good-vs-non-good comparison results or coefficient rows."""
        result = {
            "comparison": ctx.deps.api.get(
                "/rdd/group-comparison",
                {
                    "specification": specification,
                    "bandwidth_m": bandwidth_m,
                },
            )
        }
        if include_coefficients:
            result["coefficients"] = ctx.deps.api.get(
                "/rdd/group-comparison/coefficients",
                {
                    "specification": specification,
                    "bandwidth_m": bandwidth_m,
                    "term": term,
                    "limit": max(1, min(limit, 5000)),
                },
            )
        return result

    @agent.tool
    def query_diagnostics_and_benchmarks(
        ctx: RunContext[HDBAgentDeps],
        include_sign_trace: bool = False,
        include_benchmark_summary: bool = False,
        include_benchmark_results: bool = False,
        include_benchmark_best: bool = False,
        include_benchmark_metadata: bool = False,
        benchmark_variant: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return diagnostic sign-trace rows and benchmark outputs."""
        result: dict[str, Any] = {}
        if include_sign_trace:
            result["sign_trace"] = ctx.deps.api.get("/diagnostics/sign-trace")
        if include_benchmark_summary:
            result["benchmark_summary"] = ctx.deps.api.get("/benchmarks/summary")
        if include_benchmark_results:
            result["benchmark_results"] = ctx.deps.api.get(
                "/benchmarks/results",
                {
                    "variant": benchmark_variant,
                    "limit": max(1, min(limit, 1000)),
                },
            )
        if include_benchmark_best:
            result["benchmark_best"] = ctx.deps.api.get("/benchmarks/best")
        if include_benchmark_metadata:
            result["benchmark_metadata"] = ctx.deps.api.get("/benchmarks/metadata")
        return result

    @agent.tool
    def predict_resale_price(
        ctx: RunContext[HDBAgentDeps],
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the prediction schema, or call the prediction endpoint when a payload is provided."""
        if payload is None:
            return {"schema": ctx.deps.api.get("/predict/schema")}
        return {
            "schema": ctx.deps.api.get("/predict/schema"),
            "prediction": ctx.deps.api.post("/predict", payload),
        }

    return agent


def run_hdb_agent(
    user_prompt: str,
    *,
    map_context: str,
    conversation: list[dict[str, str]],
    api_base_url: str,
    api_status: dict[str, Any] | None = None,
    active_filters: dict[str, Any] | None = None,
    model_name: str | None = None,
) -> str:
    agent = build_hdb_agent(model_name)
    deps = HDBAgentDeps(
        api=HDBApiClient(api_base_url),
        map_context=map_context,
    )
    recent_conversation = conversation[-8:]
    run_prompt = "\n\n".join(
        [
            f"User question:\n{user_prompt}",
            f"Recent conversation:\n{json.dumps(recent_conversation, indent=2)}",
            f"Known API status/context:\n{json.dumps(api_status or {}, indent=2)}",
            "Use the current map context tool and API tools when they help answer the question.",
        ]
    )
    result = agent.run_sync(run_prompt, deps=deps)
    return result.output.answer
