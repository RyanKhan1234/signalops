/**
 * SignalOps Digest Type Definitions
 *
 * These types exactly mirror the digest output schema produced by the
 * Agent Orchestrator (see PRD section 3.2 and packages/agent-orchestrator/).
 * Do not modify these without a corresponding change to the API contract.
 */

/** Relevance level for key signals */
export type RelevanceLevel = 'high' | 'medium' | 'low';

/** Severity level for risks */
export type SeverityLevel = 'high' | 'medium' | 'low';

/** Confidence level for opportunities */
export type ConfidenceLevel = 'high' | 'medium' | 'low';

/** Priority level for action items */
export type PriorityLevel = 'P0' | 'P1' | 'P2';

/** Credibility level for risk sources */
export type CredibilityLevel = 'high' | 'medium' | 'low';

/** Digest type classification */
export type DigestType =
  | 'latest_news'
  | 'deep_dive'
  | 'risk_scan'
  | 'trend_watch';

/**
 * A single key signal extracted from source articles.
 * Every signal must be backed by a source article (source_url).
 */
export interface KeySignal {
  /** Human-readable signal text */
  signal: string;
  /** Direct URL to the source article */
  source_url: string;
  /** Title of the source article */
  source_title: string;
  /** ISO 8601 UTC publication date of the source article */
  published_date: string;
  /** Relevance level relative to the query */
  relevance: RelevanceLevel;
}

/**
 * A risk identified from source articles.
 * Risks represent threats or concerns detected in the competitive landscape.
 */
export interface Risk {
  /** Description of the risk */
  description: string;
  /** Severity of the risk */
  severity: SeverityLevel;
  /** How credible the sources backing this risk are */
  source_credibility?: CredibilityLevel;
  /** URLs of articles supporting this risk identification */
  source_urls: string[];
}

/**
 * An opportunity identified from source articles.
 * Opportunities represent potential strategic openings in the competitive landscape.
 */
export interface Opportunity {
  /** Description of the opportunity */
  description: string;
  /** Confidence level in this opportunity assessment */
  confidence: ConfidenceLevel;
  /** URLs of articles supporting this opportunity identification */
  source_urls: string[];
}

/**
 * A prioritized action item or follow-up.
 * Action items are derived from risks and opportunities.
 */
export interface ActionItem {
  /** The recommended action to take */
  action: string;
  /** Priority level (P0 = immediate, P1 = high, P2 = medium) */
  priority: PriorityLevel;
  /** Rationale explaining why this action is recommended */
  rationale: string;
}

/**
 * A source article referenced in the digest.
 * All sources must have valid URLs. Traceability invariant:
 * every claim in the digest must be traceable to at least one source.
 */
export interface Source {
  /** Direct URL to the article */
  url: string;
  /** Title of the article */
  title: string;
  /** ISO 8601 UTC publication date */
  published_date: string;
  /** Short excerpt from the article */
  snippet: string;
}

/**
 * A single entry in the tool execution trace.
 * Records the inputs, outputs, and latency of each MCP tool call.
 */
export interface ToolTraceEntry {
  /** Name of the MCP tool that was called */
  tool_name: string;
  /** Input parameters passed to the tool */
  input: Record<string, unknown>;
  /** Human-readable summary of the tool's output */
  output_summary: string;
  /** Round-trip latency in milliseconds */
  latency_ms: number;
  /** ISO 8601 UTC timestamp when the tool was called */
  timestamp: string;
}

/**
 * The full structured digest response from the Agent Orchestrator.
 * Returned by POST /digest.
 */
export interface DigestResponse {
  /** Classification of the digest type */
  digest_type: DigestType;
  /** The original user query */
  query: string;
  /** ISO 8601 UTC timestamp when the digest was generated */
  generated_at: string;
  /** Unique report identifier for traceability */
  report_id: string;
  /** 2-3 sentence executive summary of the digest */
  executive_summary: string;
  /** The agent's own explanation of its research process and key findings */
  research_summary?: string;
  /** Step-by-step reasoning the agent used during research */
  reasoning_steps?: string[];
  /** List of key signals extracted from source articles */
  key_signals: KeySignal[];
  /** List of identified risks */
  risks: Risk[];
  /** List of identified opportunities */
  opportunities: Opportunity[];
  /** Prioritized list of action items */
  action_items: ActionItem[];
  /** All source articles referenced in the digest */
  sources: Source[];
  /** Full tool execution trace for debugging */
  tool_trace: ToolTraceEntry[];
}

/**
 * Request payload for POST /digest.
 */
export interface DigestRequest {
  /** Natural language research prompt */
  prompt: string;
  /** User identifier for personalized context */
  user_id?: string;
}

/**
 * User profile stored in the traceability store.
 * The `context` field personalizes how the agent researches and what it highlights.
 */
export interface UserProfile {
  id: string;
  user_id: string;
  display_name: string | null;
  context: string;
  updated_at: string;
  created_at: string;
}

/**
 * Structured API error returned by the Agent Orchestrator.
 */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    retry_after_seconds?: number | null;
  };
}

/**
 * Lightweight summary of a stored digest report, returned in list responses.
 * The full digest_json is omitted; use getReportById to fetch the full report.
 */
export interface ReportSummary {
  id: string;
  report_id: string;
  digest_type: DigestType;
  query: string;
  user_id: string | null;
  generated_at: string; // ISO 8601
  created_at: string;
}

/**
 * Paginated list of report summaries returned by GET /history/api/reports.
 */
export interface PaginatedReports {
  items: ReportSummary[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * A message in the chat thread.
 */
/** Represents a real-time pipeline progress event during streaming. */
export interface StreamEvent {
  event: 'intent' | 'tool_call' | 'tool_result' | 'reasoning' | 'processing' | 'composing' | 'complete' | 'error';
  data: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'digest' | 'error' | 'streaming';
  content: string | DigestResponse | StreamEvent[];
  timestamp: string;
}
