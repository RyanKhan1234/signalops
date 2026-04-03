"""Agentic research loop using LangChain + OpenAI tool-calling.

This is the core agentic loop where the LLM (via LangChain's ChatOpenAI)
decides which tools to call, inspects results, reasons about gaps, and
iterates until it has gathered enough information to produce a high-quality
digest.

LangChain is the LLM backbone — all model interactions go through
``ChatOpenAI.bind_tools()`` and LangChain message types.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

from src.agent.tool_schemas import TOOL_SCHEMAS
from src.config import settings
from src.models.digest import Article, DetectedIntent, MCPToolResult, PlannedToolCall
from src.models.trace import ToolTraceEntry
from src.tools.mcp_client import MCPClient

logger = logging.getLogger(__name__)

StreamCallback = Callable[[str, dict[str, Any]], None] | None

RESEARCH_SYSTEM_PROMPT = """\
You are the research engine behind SignalOps — a personal research tool that
helps people stay deeply informed about topics they care about.

Your job: given a query and intent, do thorough multi-source research using
your 16 tools. You're not just searching — you're investigating.

### DATA GATHERING (fetch external information)
| Tool | What it gives you | When to use |
|------|-------------------|-------------|
| search_news | Headlines, dates, outlets | Breaking stories, recent events |
| search_company_news | Company-specific coverage | Earnings, launches, lawsuits |
| search_web | Blog posts, analyses, docs | Opinion pieces, technical write-ups |
| search_scholar | Academic papers, citations | Peer-reviewed evidence, ML research |
| search_finance | Stock price, market cap, P/E | Financial data, valuations |
| search_github | Repos, stars, languages | Open-source activity, technical momentum |
| find_videos | YouTube talks, view counts | Conference presentations, demos, tutorials |
| search_reddit | Posts, subreddits, scores | Community sentiment, real opinions |
| search_quora | Expert Q&A | Explanatory content, practitioner perspectives |
| fetch_page | Full article text | Deep-read key articles, verify claims |
| get_article_metadata | Enriched metadata for a URL | Cross-check or verify a specific source |

### ANALYTICAL (compute on data you've already gathered)
| Tool | What it computes | When to use |
|------|------------------|-------------|
| analyze_sentiment | Sentiment score, confidence, key phrases | After fetch_page — quantify the tone of coverage |
| extract_entities | Companies, people, tech, money, tickers | After fetching articles — discover names and numbers to follow up on |
| compare_sources | Cross-source similarity, shared/unique terms | After gathering 2-3 URLs — find where sources agree or disagree |
| query_past_research | Past SignalOps reports | At the START — see what we've covered before |
| calculate_trend | Mention frequency across 24h/7d/30d | Quantify whether something is gaining or losing steam |

## What makes you more than a search wrapper

The analytical tools are the whole point. Anyone can Google something.
You gather data, then actually analyze it — sentiment, entities, source
comparison, trend momentum. That analysis drives follow-up research.

Pattern: Gather → Analyze → Follow up on what the analysis reveals.
You MUST use at least 2 analytical tools per research task.

## Research Protocol

### Phase 1 — Check history & cast a wide net (Round 1)
- Start with query_past_research to see if we've looked into this before.
- Then call 2-3 search tools (search_news, search_web, etc.) to get the lay of the land.
- After receiving results, note what's interesting and what's missing.

### Phase 2 — Go deeper on the angles that matter (Round 2)
Based on what Phase 1 turned up:
- search_github for open-source activity
- search_finance for market data (if companies are involved)
- search_scholar for academic/research backing
- find_videos for conference talks or demos
- calculate_trend to see if this topic is heating up or cooling off
Use at least 2 of these plus calculate_trend.

### Phase 3 — Actually read and analyze (Round 3)
This is where the real work happens:
- fetch_page on 1-2 of the best articles from earlier
- analyze_sentiment on the fetched text
- extract_entities to discover names, amounts, technologies
- search_reddit or search_quora for what real people are saying

### Phase 4 — Cross-reference & fill gaps (Round 4)
- compare_sources on 2-3 article URLs to see where they agree or diverge
- Follow up on any NEW entities discovered by extract_entities
- Targeted searches to fill remaining holes

## Tool Diversity

Use at least 8 different tool types per task, including at least 2 analytical
tools. If fewer are genuinely applicable, explain why.

## Reasoning

Before every round after Phase 1, write 2-3 sentences:
1. What you've found so far
2. What's still missing
3. Why these tools are next

## Rules

- NEVER wrap up after a single round of tool calls.
- ALWAYS use at least 2 analytical tools.
- When done, write a thorough research summary (4-8 sentences) covering
  what you found, what the analysis revealed, and any notable patterns.
- Do NOT make things up. Only report what the tools returned.
- Do NOT repeat the same search with minor keyword tweaks.
"""


_INTENT_INSTRUCTIONS: dict[str, str] = {
    "latest_news": (
        "Tools to hit: query_past_research, search_news, search_reddit, "
        "fetch_page, analyze_sentiment, calculate_trend, plus search_finance "
        "or search_github if a company/technology is involved.\n"
        "Approach: Check what we've covered before, get the headlines, see if "
        "the topic is trending, deep-read the best article and check sentiment, "
        "see what Reddit thinks, and pull market data if relevant."
    ),
    "deep_dive": (
        "Tools to hit: query_past_research, search_news, search_web, "
        "search_scholar, search_github, search_reddit, find_videos, fetch_page, "
        "analyze_sentiment, extract_entities, compare_sources, calculate_trend.\n"
        "Approach: Full pipeline — check history, search broadly, check the "
        "trend, deep-read articles with entity extraction and sentiment, "
        "cross-reference sources, and follow up on anything new you discover."
    ),
    "risk_scan": (
        "Tools to hit: query_past_research, search_news, search_web, "
        "search_reddit, search_quora, search_finance, fetch_page, "
        "analyze_sentiment, extract_entities.\n"
        "Approach: Check history, look for concerning signals in news/web, "
        "deep-read the most alarming articles, run sentiment analysis, extract "
        "entities for companies/amounts involved, check Reddit AND Quora."
    ),
    "trend_watch": (
        "Tools to hit: query_past_research, search_news, search_github, "
        "search_scholar, find_videos, search_reddit, calculate_trend, "
        "extract_entities.\n"
        "Approach: Check history, calculate trend metrics first, then look for "
        "rising repos, conference talks, and papers. Extract entities from key "
        "articles to spot emerging players."
    ),
}


def _build_user_message(intent: DetectedIntent, user_context: str = "") -> str:
    """Build the initial user message for the research loop."""
    intent_labels = {
        "latest_news": "Latest News",
        "deep_dive": "Deep Dive",
        "risk_scan": "Risk Scan",
        "trend_watch": "Trend Watch",
    }
    label = intent_labels.get(intent.intent_type, intent.intent_type)
    entities_str = ", ".join(intent.entities) if intent.entities else "general topics"
    instructions = _INTENT_INSTRUCTIONS.get(intent.intent_type, "")

    context_section = ""
    if user_context.strip():
        context_section = (
            f"## Who this research is for\n\n"
            f"{user_context.strip()}\n\n"
            f"Tailor your tool selection, search queries, and findings to this "
            f"person's background and interests.\n\n"
        )

    return (
        f"## Research Task\n\n"
        f"**Mode**: {label}\n"
        f"**Query**: {intent.original_query}\n"
        f"**Topics**: {entities_str}\n"
        f"**Time Range**: {intent.time_range}\n\n"
        f"{context_section}"
        f"## Approach\n\n{instructions}\n\n"
        f"Start with Phase 1: query_past_research, then gather data. "
        f"Remember: use at least 8 different tool types including at "
        f"least 2 analytical tools (analyze_sentiment, extract_entities, "
        f"compare_sources, calculate_trend). Write your reasoning between rounds."
    )


def _build_langchain_llm() -> ChatOpenAI:
    """Construct a LangChain ChatOpenAI instance with tool bindings."""
    llm = ChatOpenAI(
        model=settings.research_model,
        api_key=settings.openai_api_key,
        temperature=0.1,
        max_tokens=4096,
    )
    return llm.bind_tools(TOOL_SCHEMAS)


async def run_research_loop(
    intent: DetectedIntent,
    correlation_id: str = "",
    on_event: StreamCallback = None,
    user_context: str = "",
) -> ResearchResult:
    """Execute the agentic research loop via LangChain.

    The LLM (ChatOpenAI via LangChain) decides which tools to call,
    inspects results, and iterates through multiple research phases.
    """
    llm = _build_langchain_llm()

    messages: list[BaseMessage] = [
        SystemMessage(content=RESEARCH_SYSTEM_PROMPT),
        HumanMessage(content=_build_user_message(intent, user_context=user_context)),
    ]

    all_articles: list[Article] = []
    all_traces: list[ToolTraceEntry] = []
    reasoning_steps: list[str] = []
    research_summary = ""

    max_iterations = settings.max_research_iterations

    async with MCPClient(correlation_id=correlation_id) as mcp:
        for iteration in range(max_iterations):
            logger.info(
                "[researcher] iteration %d/%d — sending %d messages",
                iteration + 1,
                max_iterations,
                len(messages),
            )

            response: AIMessage = await llm.ainvoke(messages)

            # Extract reasoning text from the response
            text_content = response.content or ""
            if isinstance(text_content, str) and text_content.strip():
                reasoning_steps.append(text_content.strip())
                if on_event:
                    _emit(on_event, "reasoning", {"step": text_content.strip()})

            tool_calls = response.tool_calls or []

            if not tool_calls:
                if text_content:
                    research_summary = text_content.strip()
                logger.info(
                    "[researcher] agent finished after %d iterations — %d articles, %d traces",
                    iteration + 1,
                    len(all_articles),
                    len(all_traces),
                )
                break

            messages.append(response)

            planned_calls: list[tuple[dict, PlannedToolCall]] = []
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})
                tool_call_id = tc["id"]

                if on_event:
                    _emit(on_event, "tool_call", {
                        "tool": tool_name,
                        "arguments": tool_args,
                        "iteration": iteration + 1,
                    })

                planned = PlannedToolCall(
                    tool_name=tool_name,
                    arguments=tool_args,
                    parallel_group=0,
                )
                planned_calls.append((tc, planned))

            async_tasks = [mcp.call_tool(pc) for _, pc in planned_calls]
            results = await asyncio.gather(*async_tasks)

            for (tc, _planned), (mcp_result, trace) in zip(planned_calls, results):
                all_articles.extend(mcp_result.articles)
                all_traces.append(trace)

                result_summary = _summarize_tool_result(mcp_result, trace)
                messages.append(
                    ToolMessage(
                        content=result_summary,
                        tool_call_id=tc["id"],
                    )
                )

                if on_event:
                    _emit(on_event, "tool_result", {
                        "tool": trace.tool_name,
                        "articles_found": len(mcp_result.articles),
                        "latency_ms": trace.latency_ms,
                        "status": trace.status,
                    })

        else:
            logger.warning(
                "[researcher] hit max iterations (%d) — returning partial results",
                max_iterations,
            )
            if not research_summary:
                research_summary = (
                    "Research completed after reaching the maximum number of "
                    "iterations. Results may be partial."
                )

    return ResearchResult(
        articles=all_articles,
        tool_traces=all_traces,
        research_summary=research_summary,
        reasoning_steps=reasoning_steps,
    )


def _summarize_tool_result(result: MCPToolResult, trace: ToolTraceEntry) -> str:
    """Build a rich, tool-specific summary of a tool result for the LLM."""
    if trace.status == "error":
        return f"Error: {trace.error or 'Tool call failed'}"

    if not result.articles:
        return f"No results found for query '{result.query}'."

    tool = trace.tool_name
    formatter = _TOOL_FORMATTERS.get(tool, _format_generic)
    return formatter(result, tool)


def _format_news(result: MCPToolResult, tool: str) -> str:
    label = "news articles" if tool == "search_news" else "company news articles"
    lines = [f"Found {len(result.articles)} {label} for '{result.query}':"]
    for i, a in enumerate(result.articles[:10], 1):
        outlet = f" [{a.source}]" if a.source else ""
        date = f" ({a.published_date})" if a.published_date else ""
        lines.append(f"{i}. {a.title}{outlet}{date}")
        lines.append(f"   URL: {a.url}")
        if a.snippet:
            lines.append(f"   {a.snippet[:300]}")
    if len(result.articles) > 10:
        lines.append(f"... and {len(result.articles) - 10} more")
    return "\n".join(lines)


def _format_github(result: MCPToolResult, _tool: str) -> str:
    lines = [f"Found {len(result.articles)} GitHub repositories for '{result.query}':"]
    for i, a in enumerate(result.articles[:10], 1):
        lines.append(f"{i}. {a.title}")
        lines.append(f"   URL: {a.url}")
        if a.snippet:
            lines.append(f"   {a.snippet[:400]}")
        if a.published_date:
            lines.append(f"   Last updated: {a.published_date}")
    if len(result.articles) > 10:
        lines.append(f"... and {len(result.articles) - 10} more repos")
    return "\n".join(lines)


def _format_scholar(result: MCPToolResult, _tool: str) -> str:
    lines = [f"Found {len(result.articles)} academic papers for '{result.query}':"]
    for i, a in enumerate(result.articles[:8], 1):
        lines.append(f'{i}. "{a.title}"')
        lines.append(f"   URL: {a.url}")
        if a.source:
            lines.append(f"   Authors/Source: {a.source}")
        if a.snippet:
            lines.append(f"   Abstract: {a.snippet[:400]}")
        if a.published_date:
            lines.append(f"   Published: {a.published_date}")
    if len(result.articles) > 8:
        lines.append(f"... and {len(result.articles) - 8} more papers")
    return "\n".join(lines)


def _format_finance(result: MCPToolResult, _tool: str) -> str:
    lines = [f"Financial data for '{result.query}':"]
    for a in result.articles[:3]:
        lines.append(f"Source: {a.title}")
        lines.append(f"URL: {a.url}")
        if a.snippet:
            lines.append(f"Metrics: {a.snippet[:600]}")
    return "\n".join(lines)


def _format_videos(result: MCPToolResult, _tool: str) -> str:
    lines = [f"Found {len(result.articles)} videos for '{result.query}':"]
    for i, a in enumerate(result.articles[:8], 1):
        channel = f" by {a.source}" if a.source else ""
        lines.append(f'{i}. "{a.title}"{channel}')
        lines.append(f"   URL: {a.url}")
        if a.snippet:
            lines.append(f"   {a.snippet[:300]}")
        if a.published_date:
            lines.append(f"   Published: {a.published_date}")
    if len(result.articles) > 8:
        lines.append(f"... and {len(result.articles) - 8} more videos")
    return "\n".join(lines)


def _format_reddit(result: MCPToolResult, _tool: str) -> str:
    lines = [f"Found {len(result.articles)} Reddit posts for '{result.query}':"]
    for i, a in enumerate(result.articles[:10], 1):
        sub = f" in {a.source}" if a.source else ""
        lines.append(f"{i}. {a.title}{sub}")
        lines.append(f"   URL: {a.url}")
        if a.snippet:
            lines.append(f"   Content: {a.snippet[:400]}")
    if len(result.articles) > 10:
        lines.append(f"... and {len(result.articles) - 10} more posts")
    return "\n".join(lines)


def _format_fetch_page(result: MCPToolResult, _tool: str) -> str:
    if not result.articles:
        return f"Could not fetch content from '{result.query}'."
    a = result.articles[0]
    lines = [
        f"Page content from: {a.title}",
        f"URL: {a.url}",
        f"Source: {a.source}" if a.source else "",
        "",
        "--- BEGIN ARTICLE TEXT ---",
        a.snippet[:2000] if a.snippet else "(No extractable text)",
        "--- END ARTICLE TEXT ---",
    ]
    return "\n".join(line for line in lines if line is not None)


def _format_analysis(result: MCPToolResult, tool: str) -> str:
    if not result.articles:
        return f"Analysis produced no output for '{result.query}'."
    a = result.articles[0]
    lines = [
        f"=== {a.title} ===",
        f"Engine: {a.source}",
        "",
        a.snippet or "(No analysis data)",
    ]
    return "\n".join(lines)


def _format_past_research(result: MCPToolResult, _tool: str) -> str:
    if not result.articles:
        return f"No past research found for '{result.query}'."
    if "No past research found" in (result.articles[0].title or ""):
        return result.articles[0].snippet or "No past research found."
    lines = [f"Found {len(result.articles)} past research report(s) matching '{result.query}':"]
    for i, a in enumerate(result.articles, 1):
        lines.append(f"{i}. {a.title}")
        lines.append(f"   {a.snippet}")
    return "\n".join(lines)


def _format_generic(result: MCPToolResult, tool: str) -> str:
    lines = [f"Found {len(result.articles)} results from {tool} for '{result.query}':"]
    for i, a in enumerate(result.articles[:8], 1):
        source = f" — {a.source}" if a.source else ""
        date = f" ({a.published_date})" if a.published_date else ""
        lines.append(f"{i}. {a.title}{source}{date}")
        lines.append(f"   URL: {a.url}")
        if a.snippet:
            lines.append(f"   {a.snippet[:300]}")
    if len(result.articles) > 8:
        lines.append(f"... and {len(result.articles) - 8} more results")
    return "\n".join(lines)


_TOOL_FORMATTERS: dict[str, Callable[[MCPToolResult, str], str]] = {
    "search_news": _format_news,
    "search_company_news": _format_news,
    "search_web": _format_generic,
    "search_scholar": _format_scholar,
    "search_finance": _format_finance,
    "search_github": _format_github,
    "find_videos": _format_videos,
    "search_reddit": _format_reddit,
    "search_quora": _format_generic,
    "fetch_page": _format_fetch_page,
    "get_article_metadata": _format_generic,
    "analyze_sentiment": _format_analysis,
    "extract_entities": _format_analysis,
    "compare_sources": _format_analysis,
    "calculate_trend": _format_analysis,
    "query_past_research": _format_past_research,
}


def _emit(callback: Callable[[str, dict[str, Any]], None], event: str, data: dict[str, Any]) -> None:
    try:
        callback(event, data)
    except Exception as exc:
        logger.warning("Stream event callback failed: %s", exc)


class ResearchResult:
    """Container for the agentic research loop output."""

    __slots__ = ("articles", "tool_traces", "research_summary", "reasoning_steps")

    def __init__(
        self,
        articles: list[Article],
        tool_traces: list[ToolTraceEntry],
        research_summary: str,
        reasoning_steps: list[str],
    ) -> None:
        self.articles = articles
        self.tool_traces = tool_traces
        self.research_summary = research_summary
        self.reasoning_steps = reasoning_steps
