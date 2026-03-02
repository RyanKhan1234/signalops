# LangChain Agent Patterns

## Architecture
- Use LangGraph for the agent state machine (not legacy AgentExecutor)
- Each processing step is a node in the graph
- State is a TypedDict passed between nodes
- Parallel tool execution where dependencies allow (use Send API)
- Guardrails node can loop back for retry (max 2 attempts)
- All nodes are async functions

## Graph Structure
```
START → detect_intent → plan_tools → execute_tools → process_articles → compose_digest → validate_guardrails → log_trace → END
                                                                                              ↑                    |
                                                                                              └────── retry ───────┘
```

## Prompt Engineering
- All prompts as Python string constants in version-controlled files
- Structured output via Pydantic models using `with_structured_output()`
- System prompts define the agent's role and constraints
- Few-shot examples for intent detection (2-3 examples per intent type)
- Temperature 0 for intent detection, 0.3 for digest composition

## Source Attribution Invariant
- EVERY claim in output MUST map to a source_url from tool results
- Store a set of all URLs returned by tools during execution
- Guardrails checks every URL in the digest against this set
- If a URL in the digest wasn't from a tool result, drop that claim
- If no sources found, return explicit "no results" — never fabricate

## State Management
```python
class AgentState(TypedDict):
    query: str
    intent: DetectedIntent
    tool_plan: list[ToolCall]
    raw_articles: list[NormalizedArticle]
    clustered_articles: dict[str, list[NormalizedArticle]]
    signals: list[KeySignal]
    risks: list[Risk]
    opportunities: list[Opportunity]
    action_items: list[ActionItem]
    digest: DigestResponse | None
    tool_trace: list[ToolTraceEntry]
    validation_errors: list[str]
    retry_count: int
```

## Error Handling
- Each node wraps its logic in try/except
- Errors are added to state, not raised (the graph continues)
- If a critical node fails (intent detection, tool execution), short-circuit to error response
- Always return a valid DigestResponse, even if it's an error digest
