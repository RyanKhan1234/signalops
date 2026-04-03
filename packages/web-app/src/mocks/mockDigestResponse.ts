/**
 * Mock digest response for development and testing.
 *
 * This mock is only used when VITE_USE_MOCK_API=true.
 * Never import this in production code -- use the real API service.
 */

import type { DigestResponse } from '../types/digest';

export const MOCK_DIGEST_RESPONSE: DigestResponse = {
  digest_type: 'deep_dive',
  query: "What's new in AI model releases this week?",
  generated_at: '2026-03-01T12:00:00Z',
  report_id: 'rpt_mock_abc123',
  executive_summary:
    "This week saw a wave of significant AI model releases: Google launched Gemini 2.0 Flash with substantially improved reasoning and multimodal capabilities, while Meta released Llama 3.2 with vision support for the first time. OpenAI quietly updated GPT-4o with improved instruction-following, and Mistral released Mistral Small 3 as a highly capable open-weight model targeting local deployment use cases.",
  key_signals: [
    {
      signal:
        'Google released Gemini 2.0 Flash, offering significantly faster inference and improved reasoning benchmarks at a lower cost tier than Gemini 1.5 Pro.',
      source_url: 'https://blog.google/technology/google-deepmind/gemini-2-flash/example/',
      source_title: 'Google launches Gemini 2.0 Flash',
      published_date: '2026-02-28T09:00:00Z',
      relevance: 'high',
    },
    {
      signal:
        'Meta released Llama 3.2 with native vision capabilities, marking the first time the Llama family supports image understanding — available as open weights.',
      source_url: 'https://ai.meta.com/blog/llama-3-2-vision/example/',
      source_title: 'Meta Llama 3.2 brings vision to open-source AI',
      published_date: '2026-02-27T14:30:00Z',
      relevance: 'high',
    },
    {
      signal:
        'Mistral AI released Mistral Small 3, a compact open-weight model claiming state-of-the-art performance in its size class, optimized for local and edge deployment.',
      source_url: 'https://mistral.ai/news/mistral-small-3/example/',
      source_title: 'Mistral Small 3: powerful and local',
      published_date: '2026-02-26T11:00:00Z',
      relevance: 'high',
    },
    {
      signal:
        'OpenAI updated GPT-4o with improved instruction-following and longer context retention, with users reporting noticeably better performance on complex multi-step tasks.',
      source_url: 'https://techcrunch.com/2026/02/gpt4o-update/example/',
      source_title: 'OpenAI quietly improves GPT-4o',
      published_date: '2026-02-25T16:00:00Z',
      relevance: 'medium',
    },
    {
      signal:
        'Anthropic published a detailed model card for Claude 3.5 Sonnet including new safety evaluations, noting improved performance on coding and agentic tasks.',
      source_url: 'https://www.anthropic.com/model-card/claude-3-5-sonnet/example/',
      source_title: 'Anthropic Claude 3.5 Sonnet model card',
      published_date: '2026-02-24T08:00:00Z',
      relevance: 'medium',
    },
  ],
  risks: [
    {
      description:
        'The rapid pace of model releases from multiple labs makes it difficult to track which model is best for a given task — benchmarks are increasingly unreliable as labs optimize specifically for them.',
      severity: 'medium',
      source_credibility: 'high',
      source_urls: [
        'https://techcrunch.com/2026/02/gpt4o-update/example/',
        'https://mistral.ai/news/mistral-small-3/example/',
      ],
    },
    {
      description:
        "Open-weight models like Llama 3.2 and Mistral Small 3 closing the gap with proprietary models could commoditize AI APIs, putting pricing pressure on OpenAI and Anthropic's core business.",
      severity: 'low',
      source_credibility: 'medium',
      source_urls: [
        'https://ai.meta.com/blog/llama-3-2-vision/example/',
      ],
    },
  ],
  opportunities: [
    {
      description:
        'Llama 3.2 vision support opens up multimodal local applications that previously required expensive proprietary APIs — worth experimenting with for image-heavy research workflows.',
      confidence: 'high',
      source_urls: [
        'https://ai.meta.com/blog/llama-3-2-vision/example/',
      ],
    },
    {
      description:
        'Gemini 2.0 Flash cost tier makes high-volume research automation significantly cheaper — could be worth benchmarking against current Claude usage for digest generation.',
      confidence: 'medium',
      source_urls: [
        'https://blog.google/technology/google-deepmind/gemini-2-flash/example/',
      ],
    },
  ],
  action_items: [
    {
      action: 'Benchmark Gemini 2.0 Flash against Claude on a sample of digest queries to compare quality and cost.',
      priority: 'P1',
      rationale: 'Lower cost per call could meaningfully reduce API spend if quality holds up for this use case.',
    },
    {
      action: 'Download and test Mistral Small 3 locally for any offline or latency-sensitive research tasks.',
      priority: 'P2',
      rationale: 'Open-weight local models are now competitive enough to be worth evaluating for personal use without API costs.',
    },
    {
      action: 'Read the Anthropic Claude 3.5 Sonnet model card safety section — relevant given recent agentic use.',
      priority: 'P2',
      rationale: 'Understanding the safety profile of models you use in agentic pipelines is worth tracking as capabilities expand.',
    },
  ],
  sources: [
    {
      url: 'https://blog.google/technology/google-deepmind/gemini-2-flash/example/',
      title: 'Google launches Gemini 2.0 Flash',
      published_date: '2026-02-28T09:00:00Z',
      snippet:
        'Google DeepMind announced Gemini 2.0 Flash, a new model in the Gemini 2.0 family offering faster inference and stronger reasoning at a lower price point than Gemini 1.5 Pro.',
    },
    {
      url: 'https://ai.meta.com/blog/llama-3-2-vision/example/',
      title: 'Meta Llama 3.2 brings vision to open-source AI',
      published_date: '2026-02-27T14:30:00Z',
      snippet:
        'Meta released Llama 3.2, the first version of the Llama model family to include native vision capabilities, available as open weights for research and commercial use.',
    },
    {
      url: 'https://mistral.ai/news/mistral-small-3/example/',
      title: 'Mistral Small 3: powerful and local',
      published_date: '2026-02-26T11:00:00Z',
      snippet:
        'Mistral AI released Mistral Small 3, a compact open-weight model optimized for local deployment, claiming top performance in its size class on standard reasoning and coding benchmarks.',
    },
    {
      url: 'https://techcrunch.com/2026/02/gpt4o-update/example/',
      title: 'OpenAI quietly improves GPT-4o',
      published_date: '2026-02-25T16:00:00Z',
      snippet:
        'OpenAI pushed a silent update to GPT-4o improving instruction-following and context retention. Users on developer forums noted the changes before any official announcement.',
    },
    {
      url: 'https://www.anthropic.com/model-card/claude-3-5-sonnet/example/',
      title: 'Anthropic Claude 3.5 Sonnet model card',
      published_date: '2026-02-24T08:00:00Z',
      snippet:
        'Anthropic published an updated model card for Claude 3.5 Sonnet covering safety evaluations, capability benchmarks, and guidance for agentic use cases.',
    },
  ],
  tool_trace: [
    {
      tool_name: 'search_news',
      input: {
        query: 'AI model releases this week',
        time_range: '7d',
        num_results: 10,
      },
      output_summary:
        'Returned 10 articles covering recent AI model releases. Top topics: Gemini 2.0 Flash (3 articles), Llama 3.2 vision (3 articles), Mistral Small 3 (2 articles), GPT-4o update (2 articles).',
      latency_ms: 1121,
      timestamp: '2026-03-01T11:59:45Z',
    },
    {
      tool_name: 'search_news',
      input: {
        query: '"AI models" OR "LLMs" OR "foundation models" analysis update development',
        time_range: '7d',
        num_results: 10,
      },
      output_summary:
        'Returned 10 articles on broader AI model landscape. 5 overlapped with first search; 5 new articles added including Anthropic model card and benchmark analysis pieces.',
      latency_ms: 934,
      timestamp: '2026-03-01T11:59:47Z',
    },
  ],
};

/**
 * Simulates API latency for a more realistic development experience.
 * Returns the mock digest response after a delay.
 */
export async function getMockDigestResponse(
  _prompt: string
): Promise<DigestResponse> {
  await new Promise((resolve) => setTimeout(resolve, 2500));
  return {
    ...MOCK_DIGEST_RESPONSE,
    query: _prompt,
    generated_at: new Date().toISOString(),
    report_id: `rpt_mock_${Date.now()}`,
  };
}
