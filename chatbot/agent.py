from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from .api_client import HDBApiClient


DEFAULT_AGENT_MODEL = "openai:gpt-4.1-mini"

AGENT_INSTRUCTIONS = """
You are an HDB resale assistant for non-technical stakeholders. Answer from
the current map context and the FastAPI tools. Explain prices, towns, school
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
        }

    @agent.tool
    def query_resales(
        ctx: RunContext[HDBAgentDeps],
        town: list[str] | None = None,
        flat_type: list[str] | None = None,
        flat_model: list[str] | None = None,
        month: list[str] | None = None,
        month_from: str | None = None,
        month_to: str | None = None,
        min_resale_price: float | None = None,
        max_resale_price: float | None = None,
        min_good_school_count_1km: float | None = None,
        max_good_school_count_1km: float | None = None,
        group_by: str | None = None,
        include_rows: bool = False,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Return resale summary statistics, and optionally sample rows, using only explicit user filters."""
        params = {
            "town": town,
            "flat_type": flat_type,
            "flat_model": flat_model,
            "month": month,
            "month_from": month_from,
            "month_to": month_to,
            "min_resale_price": min_resale_price,
            "max_resale_price": max_resale_price,
            "min_good_school_count_1km": min_good_school_count_1km,
            "max_good_school_count_1km": max_good_school_count_1km,
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
