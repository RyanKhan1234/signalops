/**
 * Tests for the API service layer.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { submitDigestRequest, DigestApiError } from '../services/api';
import { MOCK_DIGEST_RESPONSE } from '../mocks/mockDigestResponse';

describe('submitDigestRequest', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('sends a POST request to /digest with the prompt', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => MOCK_DIGEST_RESPONSE,
    });
    global.fetch = mockFetch;

    await submitDigestRequest({ prompt: 'test prompt' });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/digest');
    expect(options.method).toBe('POST');

    const body = JSON.parse(options.body as string) as { prompt: string };
    expect(body.prompt).toBe('test prompt');
  });

  it('sets Content-Type and Accept headers', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => MOCK_DIGEST_RESPONSE,
    });
    global.fetch = mockFetch;

    await submitDigestRequest({ prompt: 'test' });

    const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = options.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['Accept']).toBe('application/json');
    expect(headers['X-Request-ID']).toBeDefined();
  });

  it('returns a DigestResponse on success', async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: async () => MOCK_DIGEST_RESPONSE,
    } as Response);

    const result = await submitDigestRequest({ prompt: 'test' });
    expect(result.report_id).toBe(MOCK_DIGEST_RESPONSE.report_id);
    expect(result.digest_type).toBe('weekly_report');
  });

  it('throws DigestApiError with NETWORK_ERROR code on fetch failure', async () => {
    vi.mocked(global.fetch).mockRejectedValue(new Error('Network error'));

    await expect(submitDigestRequest({ prompt: 'test' })).rejects.toThrow(
      DigestApiError
    );

    try {
      await submitDigestRequest({ prompt: 'test' });
    } catch (err) {
      expect(err instanceof DigestApiError).toBe(true);
      if (err instanceof DigestApiError) {
        expect(err.code).toBe('NETWORK_ERROR');
      }
    }
  });

  it('throws DigestApiError on non-ok HTTP response with API error body', async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({
        error: {
          code: 'INVALID_PROMPT',
          message: 'Prompt is too short',
          details: {},
          retry_after_seconds: null,
        },
      }),
    } as Response);

    try {
      await submitDigestRequest({ prompt: 'hi' });
      expect.fail('Should have thrown');
    } catch (err) {
      expect(err instanceof DigestApiError).toBe(true);
      if (err instanceof DigestApiError) {
        expect(err.code).toBe('INVALID_PROMPT');
        expect(err.message).toBe('Prompt is too short');
        expect(err.httpStatus).toBe(400);
      }
    }
  });

  it('throws DigestApiError with REQUEST_CANCELLED when aborted', async () => {
    const controller = new AbortController();
    vi.mocked(global.fetch).mockImplementation(() => {
      const abortError = new DOMException('Aborted', 'AbortError');
      return Promise.reject(abortError);
    });

    try {
      await submitDigestRequest({ prompt: 'test' }, controller.signal);
      expect.fail('Should have thrown');
    } catch (err) {
      expect(err instanceof DigestApiError).toBe(true);
      if (err instanceof DigestApiError) {
        expect(err.code).toBe('REQUEST_CANCELLED');
      }
    }
  });

  it('throws DigestApiError with INVALID_RESPONSE_FORMAT for response missing report_id', async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ some_unexpected_field: true }),
    } as Response);

    try {
      await submitDigestRequest({ prompt: 'test' });
      expect.fail('Should have thrown');
    } catch (err) {
      expect(err instanceof DigestApiError).toBe(true);
      if (err instanceof DigestApiError) {
        expect(err.code).toBe('INVALID_RESPONSE_FORMAT');
      }
    }
  });
});

describe('DigestApiError', () => {
  it('constructs with a message and code', () => {
    const err = new DigestApiError('test message', 'TEST_CODE');
    expect(err.message).toBe('test message');
    expect(err.code).toBe('TEST_CODE');
    expect(err.name).toBe('DigestApiError');
    expect(err instanceof Error).toBe(true);
  });

  it('stores optional fields', () => {
    const err = new DigestApiError('msg', 'CODE', {
      details: { foo: 'bar' },
      retryAfterSeconds: 30,
      httpStatus: 429,
    });
    expect(err.details).toEqual({ foo: 'bar' });
    expect(err.retryAfterSeconds).toBe(30);
    expect(err.httpStatus).toBe(429);
  });
});
