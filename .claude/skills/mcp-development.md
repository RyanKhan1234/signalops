# MCP Server Development Patterns

## Framework
Use Python FastMCP for the MCP server. Key principles:
- Clear, descriptive tool names with consistent prefixes
- Concise tool descriptions that help agents discover the right tool
- Actionable error messages that guide toward solutions
- Return focused, relevant data — avoid dumping raw API responses
- Use Pydantic models for all inputs and outputs

## Transport
- Default to SSE transport for inter-service communication in Docker
- stdio for local development/testing

## Tool Design
- Each tool does ONE thing well
- Input validation happens BEFORE any external call
- Every response includes a `request_id` for traceability
- Cache-aware: responses indicate if they were served from cache

## Error Handling
- All errors are structured JSON with code, message, details
- Never expose internal stack traces to the caller
- Include `retry_after_seconds` on rate limit errors
- Timeout errors should suggest the caller retry with a smaller query

## Testing
- Never call real external APIs in tests
- Use `respx` or `httpx` mocking for async HTTP tests
- Store sample API responses as JSON fixtures
- Test every middleware layer independently
