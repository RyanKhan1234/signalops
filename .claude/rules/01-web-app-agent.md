# Web App Agent Rules

> You are the **web-app-agent**. You own `packages/web-app/` and work on the `feat/web-app` branch.

## Your Scope

You build and maintain the React frontend for SignalOps. You do NOT touch the Agent Orchestrator, MCP Wrapper, or Traceability Store packages.

## Tech Stack

- **Framework:** React 18+ with TypeScript (strict mode)
- **Build Tool:** Vite
- **Styling:** Tailwind CSS
- **HTTP Client:** Fetch API (native) or axios
- **Testing:** Vitest + React Testing Library
- **Linting:** ESLint + Prettier

## Package Structure

```
packages/web-app/
├── src/
│   ├── components/
│   │   ├── chat/            # Chat input, message list, prompt suggestions
│   │   ├── digest/          # Digest viewer sections (summary, signals, risks, etc.)
│   │   ├── debug/           # Debug panel, tool trace viewer
│   │   └── common/          # Shared UI components (buttons, cards, loaders)
│   ├── hooks/               # Custom React hooks
│   ├── services/            # API client layer
│   ├── types/               # TypeScript type definitions
│   ├── utils/               # Utility functions
│   ├── App.tsx
│   └── main.tsx
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── .env.example
```

## Key Responsibilities

### 1. Chat Interface (`/chat` route)

- Text input with submit button and keyboard shortcut (Cmd/Ctrl + Enter)
- Prompt suggestions for common queries: "Daily digest for [company]", "Risk alert: [topic]", "What's new with [competitor]?"
- Message history showing user prompts and digest responses in a conversational thread
- Loading states with progress indicators during digest generation

### 2. Digest Viewer

Render the structured digest JSON into clearly separated sections:

- **Executive Summary** — Prominent text block at top
- **Key Signals** — Cards with signal text, source link, published date, relevance badge (high/medium/low)
- **Risks** — Cards with severity indicators (red/yellow/green)
- **Opportunities** — Cards with confidence indicators
- **Action Items** — Ordered list with priority badges (P0/P1/P2)
- **Sources** — Compact list of all referenced articles with external links
- **Tool Trace** — Collapsible accordion showing each tool call with its input, output summary, and latency

### 3. Debug Panel

- Toggle-able side panel or bottom drawer
- Shows raw JSON of the full digest response
- Per-tool-call breakdown: tool name, input params, output summary, latency in ms
- Correlation/report ID displayed prominently

### 4. API Integration

**Single endpoint to consume:**

```typescript
// POST /api/digest
interface DigestRequest {
  prompt: string;
  // future: user_id, preferences
}

interface DigestResponse {
  digest_type: 'daily_digest' | 'weekly_report' | 'risk_alert' | 'competitor_monitor';
  query: string;
  generated_at: string;
  report_id: string;
  executive_summary: string;
  key_signals: KeySignal[];
  risks: Risk[];
  opportunities: Opportunity[];
  action_items: ActionItem[];
  sources: Source[];
  tool_trace: ToolTraceEntry[];
}
```

- Base URL configured via `VITE_API_BASE_URL` environment variable
- Handle loading, success, and error states for all API calls
- Support future SSE streaming for long-running digests

## Type Definitions

Define and export all shared types in `src/types/`:

```typescript
// src/types/digest.ts
export interface KeySignal {
  signal: string;
  source_url: string;
  source_title: string;
  published_date: string;
  relevance: 'high' | 'medium' | 'low';
}

export interface Risk {
  description: string;
  severity: 'high' | 'medium' | 'low';
  source_urls: string[];
}

export interface Opportunity {
  description: string;
  confidence: 'high' | 'medium' | 'low';
  source_urls: string[];
}

export interface ActionItem {
  action: string;
  priority: 'P0' | 'P1' | 'P2';
  rationale: string;
}

export interface Source {
  url: string;
  title: string;
  published_date: string;
  snippet: string;
}

export interface ToolTraceEntry {
  tool_name: string;
  input: Record<string, unknown>;
  output_summary: string;
  latency_ms: number;
  timestamp: string;
}
```

## Design Guidelines

- Clean, professional, dashboard-style UI — think "ops tool", not consumer app
- Light theme by default with clear typographic hierarchy
- Responsive but optimized for desktop (primary use case is ops team at desks)
- Use color coding for severity/relevance/priority badges consistently
- Subtle animations for loading states and section reveals (no flashy transitions)
- Accessible: proper ARIA labels, keyboard navigation, sufficient color contrast

## Rules

1. **Never mock the API in production code.** Use a separate mock service for development.
2. **Type everything.** No `any` types unless absolutely unavoidable (and documented why).
3. **Keep components focused.** Each component does one thing. Compose for complexity.
4. **API layer is isolated.** All HTTP calls go through `src/services/`. Components never call fetch directly.
5. **Error boundaries.** Wrap major sections in React error boundaries with user-friendly fallbacks.
6. **Environment variables.** All config via `VITE_*` env vars. Never hardcode URLs or keys.
