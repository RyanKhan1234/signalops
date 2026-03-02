/**
 * SignalOps API Service Layer
 *
 * All HTTP communication with the Agent Orchestrator goes through this module.
 * Components must never call fetch() directly — use these service functions instead.
 *
 * Base URL is configured via the VITE_API_BASE_URL environment variable.
 */

import type { DigestRequest, DigestResponse, ApiError, PaginatedReports } from '../types/digest';

const BASE_URL = import.meta.env['VITE_API_BASE_URL'] ?? 'http://localhost:8000';

/**
 * Base URL for the Traceability Store, proxied through nginx under /history/.
 * In development (direct Vite), falls back to the docker-mapped port.
 */
const HISTORY_BASE_URL = import.meta.env['VITE_HISTORY_BASE_URL'] ?? '/history';

/**
 * Generates a random correlation ID for request tracing.
 */
function generateRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Type guard to check if a response body is an ApiError.
 */
function isApiError(body: unknown): body is ApiError {
  return (
    typeof body === 'object' &&
    body !== null &&
    'error' in body &&
    typeof (body as ApiError).error === 'object'
  );
}

/**
 * Custom error class for API failures with structured error info.
 */
export class DigestApiError extends Error {
  public readonly code: string;
  public readonly details?: Record<string, unknown>;
  public readonly retryAfterSeconds?: number | null;
  public readonly httpStatus?: number;

  constructor(
    message: string,
    code: string,
    options?: {
      details?: Record<string, unknown>;
      retryAfterSeconds?: number | null;
      httpStatus?: number;
    }
  ) {
    super(message);
    this.name = 'DigestApiError';
    this.code = code;
    this.details = options?.details;
    this.retryAfterSeconds = options?.retryAfterSeconds;
    this.httpStatus = options?.httpStatus;
  }
}

/**
 * Submits a natural language prompt to the Agent Orchestrator and returns
 * a structured digest response.
 *
 * @param request - The digest request containing the user's prompt
 * @param signal - Optional AbortSignal to cancel the request
 * @returns A structured DigestResponse
 * @throws DigestApiError on API or network errors
 */
export async function submitDigestRequest(
  request: DigestRequest,
  signal?: AbortSignal
): Promise<DigestResponse> {
  const requestId = generateRequestId();

  let response: Response;

  try {
    response = await fetch(`${BASE_URL}/digest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-Request-ID': requestId,
      },
      body: JSON.stringify(request),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new DigestApiError('Request was cancelled', 'REQUEST_CANCELLED');
    }
    throw new DigestApiError(
      'Unable to reach the SignalOps API. Please check your connection.',
      'NETWORK_ERROR',
      { details: { originalError: String(err) } }
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new DigestApiError(
      `API returned an invalid response (HTTP ${response.status})`,
      'INVALID_RESPONSE',
      { httpStatus: response.status }
    );
  }

  if (!response.ok) {
    if (isApiError(body)) {
      throw new DigestApiError(body.error.message, body.error.code, {
        details: body.error.details,
        retryAfterSeconds: body.error.retry_after_seconds,
        httpStatus: response.status,
      });
    }
    throw new DigestApiError(
      `API request failed with status ${response.status}`,
      'HTTP_ERROR',
      { httpStatus: response.status }
    );
  }

  // Validate minimal shape of the response
  if (!body || typeof body !== 'object' || !('report_id' in body)) {
    throw new DigestApiError(
      'API returned an unexpected response format',
      'INVALID_RESPONSE_FORMAT'
    );
  }

  return body as DigestResponse;
}

/**
 * Health-check against the Agent Orchestrator.
 * Returns true if the service is reachable.
 */
export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Fetches a paginated list of past digest reports from the Traceability Store.
 *
 * @param params - Optional filter/pagination parameters
 * @returns Paginated list of report summaries
 * @throws DigestApiError on network or API errors
 */
export async function listReports(params?: {
  limit?: number;
  offset?: number;
  digest_type?: string;
}): Promise<PaginatedReports> {
  const url = new URL(`${HISTORY_BASE_URL}/api/reports`, window.location.origin);
  if (params?.limit !== undefined) url.searchParams.set('limit', String(params.limit));
  if (params?.offset !== undefined) url.searchParams.set('offset', String(params.offset));
  if (params?.digest_type) url.searchParams.set('digest_type', params.digest_type);

  let response: Response;
  try {
    response = await fetch(url.toString(), {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
  } catch (err) {
    throw new DigestApiError(
      'Unable to reach the history service. Please check your connection.',
      'NETWORK_ERROR',
      { details: { originalError: String(err) } }
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new DigestApiError(
      `History API returned an invalid response (HTTP ${response.status})`,
      'INVALID_RESPONSE',
      { httpStatus: response.status }
    );
  }

  if (!response.ok) {
    if (isApiError(body)) {
      throw new DigestApiError(body.error.message, body.error.code, {
        details: body.error.details,
        retryAfterSeconds: body.error.retry_after_seconds,
        httpStatus: response.status,
      });
    }
    throw new DigestApiError(
      `History API request failed with status ${response.status}`,
      'HTTP_ERROR',
      { httpStatus: response.status }
    );
  }

  return body as PaginatedReports;
}

/**
 * Fetches the full digest detail for a single report by its report_id.
 * Extracts and returns the digest_json field, which is a DigestResponse.
 *
 * @param reportId - The human-readable report ID (e.g. "rpt_abc123")
 * @returns The full DigestResponse stored in digest_json
 * @throws DigestApiError on network, 404, or API errors
 */
export async function getReportById(reportId: string): Promise<DigestResponse> {
  let response: Response;
  try {
    response = await fetch(`${HISTORY_BASE_URL}/api/reports/${encodeURIComponent(reportId)}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
  } catch (err) {
    throw new DigestApiError(
      'Unable to reach the history service. Please check your connection.',
      'NETWORK_ERROR',
      { details: { originalError: String(err) } }
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new DigestApiError(
      `History API returned an invalid response (HTTP ${response.status})`,
      'INVALID_RESPONSE',
      { httpStatus: response.status }
    );
  }

  if (!response.ok) {
    if (isApiError(body)) {
      throw new DigestApiError(body.error.message, body.error.code, {
        details: body.error.details,
        retryAfterSeconds: body.error.retry_after_seconds,
        httpStatus: response.status,
      });
    }
    throw new DigestApiError(
      `History API request failed with status ${response.status}`,
      'HTTP_ERROR',
      { httpStatus: response.status }
    );
  }

  const detail = body as { digest_json: DigestResponse };
  return detail.digest_json;
}
