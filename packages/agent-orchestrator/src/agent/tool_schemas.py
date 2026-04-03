"""Tool definitions for the agentic research loop (OpenAI function-calling format).

These schemas are passed to ``ChatOpenAI(...).bind_tools(TOOL_SCHEMAS)`` via
LangChain so the LLM can decide which MCP tools to call, inspect results,
and iterate.

Format follows the OpenAI function-calling specification which LangChain's
``bind_tools()`` accepts natively.
"""

from __future__ import annotations

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": (
                "Search recent news articles. Returns headlines, URLs, publication "
                "dates, source outlets, and snippets. Use for breaking news, "
                "recent developments, and time-sensitive stories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The news search query (max 200 chars).",
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["1d", "7d", "30d", "1y"],
                        "description": "How far back to search. Default '7d'.",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results (1-50, default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_company_news",
            "description": (
                "Search news specific to a named company or organization. "
                "Optionally filter by topic keywords like 'earnings', 'lawsuit', "
                "'product launch'. Prefer this over search_news when the query "
                "is clearly about a single company."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company or organization name.",
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["1d", "7d", "30d", "1y"],
                        "description": "How far back to search. Default '7d'.",
                    },
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional topic keywords to narrow results.",
                    },
                },
                "required": ["company"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_metadata",
            "description": (
                "Fetch metadata for a specific article URL you already have. "
                "Use when you want to verify or enrich a URL from earlier results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full HTTP/HTTPS URL of the article.",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "General Google web search. Returns organic results including "
                "blog posts, analyses, documentation, and landing pages. Use "
                "when you need broader coverage beyond news, such as opinion "
                "pieces, technical write-ups, or company pages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The web search query (max 200 chars).",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results (1-50, default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_scholar",
            "description": (
                "Search Google Scholar for academic papers and research. Returns "
                "paper titles, authors, citation counts, and abstracts. Best for "
                "AI/ML, science, medical, and technical deep-dives where peer-"
                "reviewed evidence matters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The academic search query (max 200 chars).",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results (1-50, default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_finance",
            "description": (
                "Search Google Finance for market data on a stock ticker or "
                "company. Returns price, market cap, P/E, and key metrics. Use "
                "when the research involves financial performance or stock movement."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Ticker symbol or company name (e.g. 'AAPL:NASDAQ' "
                            "or 'Tesla Inc')."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_videos",
            "description": (
                "Search YouTube for relevant videos. Returns titles, channel "
                "names, view counts, and links. Use for finding talks, demos, "
                "tutorials, or conference presentations on a topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The video search query (max 200 chars).",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results (1-50, default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_github",
            "description": (
                "Search GitHub repositories. Returns repo names, descriptions, "
                "star counts, and primary languages. Use to discover open-source "
                "projects, track developer activity, or find code related to "
                "a technology."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The repository search query (max 200 chars).",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results (1-50, default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_reddit",
            "description": (
                "Search Reddit posts and discussions. Returns post titles, "
                "subreddits, scores, and content snippets. Best for community "
                "sentiment, real user experiences, complaints, and grassroots "
                "opinions that don't appear in mainstream news."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (max 200 chars).",
                    },
                    "subreddit": {
                        "type": "string",
                        "description": (
                            "Optional subreddit to restrict search "
                            "(e.g. 'MachineLearning')."
                        ),
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results (1-50, default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_quora",
            "description": (
                "Search Quora for Q&A content. Returns questions, answers, and "
                "expert opinions. Use for explanatory content, especially on "
                "business strategy, career, finance, or non-technical topics "
                "where Reddit coverage is thin."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (max 200 chars).",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results (1-50, default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": (
                "Fetch a web page and extract its plain-text content (up to "
                "5000 chars). Use this to read the full body of a specific "
                "article or page when a snippet isn't enough. Requires a URL "
                "you already have from a previous search result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full HTTP/HTTPS URL to fetch.",
                    },
                },
                "required": ["url"],
            },
        },
    },
    # --- Analytical / computational tools (NOT search wrappers) ---
    {
        "type": "function",
        "function": {
            "name": "analyze_sentiment",
            "description": (
                "Run NLP sentiment analysis on a block of text. Returns a "
                "sentiment score (-1 to +1), label (positive/negative/mixed/"
                "neutral), confidence, and key positive/negative phrases. "
                "Use this on article text from fetch_page results, or on "
                "Reddit/Quora content, to quantify public sentiment about "
                "a topic. This is a computational tool, not a search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": (
                            "The text to analyze for sentiment. Can be article "
                            "content, search snippets, or any text block."
                        ),
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_entities",
            "description": (
                "Extract named entities from text using NER (Named Entity "
                "Recognition). Identifies: organizations, people, technologies, "
                "monetary amounts, percentages, stock tickers, and dates. "
                "Use this to discover entities mentioned in articles that you "
                "can then research further with other tools. This is a "
                "computational NLP tool, not a search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to analyze for entity extraction.",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_sources",
            "description": (
                "Cross-reference 2-3 articles by URL. Fetches each article, "
                "extracts key terms, and computes: content similarity (Jaccard), "
                "shared themes, and unique angles per source. Use this to verify "
                "whether multiple sources agree or to identify what each source "
                "uniquely contributes. This is a cross-referencing analytical "
                "tool, not a search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "2-3 article URLs to compare. Must be URLs you "
                            "already have from previous search results."
                        ),
                    },
                },
                "required": ["urls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_past_research",
            "description": (
                "Search SignalOps' own archive of past digest reports for "
                "related research. Returns previous digests matching the "
                "query topic, showing what was found before. Use this to "
                "build on prior findings and provide continuity across "
                "research sessions. This queries internal system state, "
                "not the web."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Topic or keywords to search in past digests.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_trend",
            "description": (
                "Calculate mention frequency trend for a topic across three "
                "time windows (24h, 7d, 30d). Returns: article counts per "
                "window, daily rates, acceleration percentage, recency spike "
                "factor, and an overall trend label (SURGING/GROWING/STABLE/"
                "DECLINING/FADING). Use this to quantify whether a topic is "
                "gaining or losing momentum. This is a statistical computation "
                "tool that uses search data as input."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The topic to calculate trends for.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]
