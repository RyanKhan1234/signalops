/**
 * SignalOps API Service Layer
 *
 * All HTTP communication with the Agent Orchestrator goes through this module.
 * Components must never call fetch() directly — use these service functions instead.
 *
 * Base URL is configured via the VITE_API_BASE_URL environment variable.
 */

import type { DigestRequest, DigestResponse, ApiError, PaginatedReports, UserProfile } from '../types/digest';

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
 * Submits a prompt to the streaming digest endpoint and returns parsed SSE events
 * via a callback as they arrive. The final "complete" event contains the full digest.
 *
 * @param request - The digest request containing the user's prompt
 * @param onEvent - Callback invoked for each SSE event
 * @param signal - Optional AbortSignal to cancel the stream
 * @returns The final DigestResponse (also delivered via the "complete" event)
 * @throws DigestApiError on network or stream errors
 */
export async function submitDigestStream(
  request: DigestRequest,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal
): Promise<DigestResponse> {
  const requestId = generateRequestId();

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/digest/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
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

  if (!response.ok) {
    throw new DigestApiError(
      `API request failed with status ${response.status}`,
      'HTTP_ERROR',
      { httpStatus: response.status }
    );
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new DigestApiError('No response body', 'INVALID_RESPONSE');
  }

  const decoder = new TextDecoder();
  let buffer = '';
  let finalDigest: DigestResponse | null = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      let currentEvent = '';
      let currentData = '';

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          currentData = line.slice(6);
        } else if (line === '' && currentEvent && currentData) {
          try {
            const parsed = JSON.parse(currentData);
            onEvent(currentEvent, parsed);

            if (currentEvent === 'complete') {
              finalDigest = parsed as DigestResponse;
            }
          } catch {
            // Skip malformed JSON
          }
          currentEvent = '';
          currentData = '';
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  if (!finalDigest) {
    throw new DigestApiError(
      'Stream ended without a complete digest',
      'INCOMPLETE_STREAM'
    );
  }

  return finalDigest;
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
 * Saves a digest report to the Traceability Store history.
 *
 * @param digest - The DigestResponse to save
 * @param query - The original query string used to generate the digest
 * @returns { alreadySaved: true } if the report was already saved (409), { alreadySaved: false } on success (201)
 * @throws DigestApiError on network or unexpected API errors
 */
export async function saveReport(
  digest: DigestResponse,
  query: string
): Promise<{ alreadySaved: boolean }> {
  const report_id = digest.report_id ?? crypto.randomUUID();
  const url = new URL(`${HISTORY_BASE_URL}/api/reports`, window.location.origin);

  const payload = {
    report_id,
    digest_type: digest.digest_type,
    query,
    digest_json: digest,
    generated_at: digest.generated_at,
    user_id: null,
  };

  let response: Response;
  try {
    response = await fetch(url.toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    throw new DigestApiError(
      'Unable to reach the history service. Please check your connection.',
      'NETWORK_ERROR',
      { details: { originalError: String(err) } }
    );
  }

  // 409 = already saved — treat as success
  if (response.status === 409) {
    return { alreadySaved: true };
  }

  if (response.status === 201) {
    return { alreadySaved: false };
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


/**
 * Fetches a user profile from the Traceability Store.
 * Returns null if the profile doesn't exist (404).
 */
export async function getUserProfile(userId: string): Promise<UserProfile | null> {
  const url = new URL(
    `${HISTORY_BASE_URL}/api/profiles/${encodeURIComponent(userId)}`,
    window.location.origin,
  );

  try {
    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    if (response.status === 404) return null;

    if (!response.ok) {
      throw new DigestApiError(
        `Profile API returned status ${response.status}`,
        'HTTP_ERROR',
        { httpStatus: response.status },
      );
    }

    return (await response.json()) as UserProfile;
  } catch (err) {
    if (err instanceof DigestApiError) throw err;
    return null;
  }
}


/**
 * Creates or updates a user profile in the Traceability Store.
 */
export async function saveUserProfile(
  userId: string,
  data: { display_name?: string | null; context: string },
): Promise<UserProfile> {
  const url = new URL(
    `${HISTORY_BASE_URL}/api/profiles/${encodeURIComponent(userId)}`,
    window.location.origin,
  );

  const response = await fetch(url.toString(), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new DigestApiError(
      `Failed to save profile (HTTP ${response.status})`,
      'HTTP_ERROR',
      { httpStatus: response.status },
    );
  }

  return (await response.json()) as UserProfile;
}
