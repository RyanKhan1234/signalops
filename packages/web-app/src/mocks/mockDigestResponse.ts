/**
 * Mock digest response for development and testing.
 *
 * This mock is only used when VITE_USE_MOCK_API=true.
 * It mirrors the example flow from PRD section 4 (Walmart Connect weekly report).
 * Never import this in production code -- use the real API service.
 */

import type { DigestResponse } from '../types/digest';

export const MOCK_DIGEST_RESPONSE: DigestResponse = {
  digest_type: 'weekly_report',
  query: 'Anything important about Walmart Connect this week?',
  generated_at: '2026-03-01T12:00:00Z',
  report_id: 'rpt_mock_abc123',
  executive_summary:
    "Walmart Connect had a significant week, announcing expanded self-serve ad capabilities and a new API integration program targeting mid-market retail brands. These moves signal a strategic push to deepen its retail media ecosystem and compete more directly with Amazon Advertising and Criteo in the self-serve segment. Revenue from Walmart Connect grew an estimated 28% YoY according to analyst commentary.",
  key_signals: [
    {
      signal:
        'Walmart Connect launches expanded self-serve ad platform with new targeting capabilities for mid-market brands.',
      source_url:
        'https://www.retaildive.com/news/walmart-connect-self-serve-ad-platform-2026/example/',
      source_title: 'Walmart Connect Expands Self-Serve Ad Platform',
      published_date: '2026-02-28T09:00:00Z',
      relevance: 'high',
    },
    {
      signal:
        'Walmart Connect announces API integration program enabling third-party DSPs to access Walmart first-party shopper data.',
      source_url:
        'https://www.adexchanger.com/retail-media/walmart-connect-api-2026/example/',
      source_title: 'Walmart Connect Opens API to Third-Party DSPs',
      published_date: '2026-02-27T14:30:00Z',
      relevance: 'high',
    },
    {
      signal:
        'Analyst report estimates Walmart Connect revenue grew 28% YoY in Q4 2025, outpacing broader retail media market growth.',
      source_url:
        'https://www.emarketer.com/content/walmart-connect-q4-2025/example/',
      source_title: 'Walmart Connect Q4 2025 Revenue Analysis',
      published_date: '2026-02-26T11:00:00Z',
      relevance: 'high',
    },
    {
      signal:
        'Walmart Connect adds new video ad formats to its in-store screen network, increasing premium inventory supply.',
      source_url:
        'https://www.marketingweek.com/walmart-connect-video-ads/example/',
      source_title: 'Walmart Connect Adds Video to In-Store Screens',
      published_date: '2026-02-25T16:00:00Z',
      relevance: 'medium',
    },
    {
      signal:
        'Walmart Connect hires former Amazon Advertising VP as new Head of Advertiser Solutions.',
      source_url:
        'https://www.linkedin.com/news/walmart-connect-hire/example/',
      source_title: 'Walmart Connect Poaches Amazon Advertising Exec',
      published_date: '2026-02-24T08:00:00Z',
      relevance: 'medium',
    },
  ],
  risks: [
    {
      description:
        "Walmart Connect self-serve platform expansion may pressure competitor ad margins as brands reallocate budgets from smaller retail media networks to Walmart's scale.",
      severity: 'high',
      source_urls: [
        'https://www.retaildive.com/news/walmart-connect-self-serve-ad-platform-2026/example/',
        'https://www.emarketer.com/content/walmart-connect-q4-2025/example/',
      ],
    },
    {
      description:
        "New API integrations could accelerate DSP consolidation around Walmart's first-party data, reducing leverage for independent retail media platforms.",
      severity: 'high',
      source_urls: [
        'https://www.adexchanger.com/retail-media/walmart-connect-api-2026/example/',
      ],
    },
    {
      description:
        'Recruitment of Amazon Advertising talent signals intensified competition for ad tech expertise and potential acceleration in platform capabilities.',
      severity: 'medium',
      source_urls: [
        'https://www.linkedin.com/news/walmart-connect-hire/example/',
      ],
    },
  ],
  opportunities: [
    {
      description:
        'New API integration program presents a potential partnership opening to position as a preferred third-party measurement or attribution partner for Walmart Connect campaigns.',
      confidence: 'high',
      source_urls: [
        'https://www.adexchanger.com/retail-media/walmart-connect-api-2026/example/',
      ],
    },
    {
      description:
        "Walmart Connect's expansion into mid-market self-serve creates an opening to position complementary planning and optimization tools for brands new to Walmart's ecosystem.",
      confidence: 'medium',
      source_urls: [
        'https://www.retaildive.com/news/walmart-connect-self-serve-ad-platform-2026/example/',
      ],
    },
  ],
  action_items: [
    {
      action:
        'Evaluate Walmart Connect API integration program and submit a partnership application as a third-party measurement partner within the next 2 weeks.',
      priority: 'P0',
      rationale:
        'Early mover advantage in the API program could secure preferred partner status before competitors. The integration opens direct access to Walmart first-party shopper data for campaign measurement.',
    },
    {
      action:
        'Conduct competitive impact analysis: model how Walmart Connect self-serve budget reallocation from mid-market brands affects our current pipeline in the retail media segment.',
      priority: 'P1',
      rationale:
        'Self-serve platform lowers the barrier to entry for Walmart advertising. If mid-market brands in our pipeline shift spend to Walmart Connect, we need to understand the revenue risk before Q2 planning.',
    },
    {
      action:
        'Brief the sales team on Walmart Connect platform expansions with updated competitive positioning deck for RevOps conversations with enterprise prospects.',
      priority: 'P2',
      rationale:
        'Sales teams need current competitive context to handle objections from prospects evaluating Walmart Connect alternatives.',
    },
  ],
  sources: [
    {
      url: 'https://www.retaildive.com/news/walmart-connect-self-serve-ad-platform-2026/example/',
      title: 'Walmart Connect Expands Self-Serve Ad Platform',
      published_date: '2026-02-28T09:00:00Z',
      snippet:
        'Walmart Connect announced a significant expansion of its self-serve advertising platform on Thursday, adding new audience targeting capabilities specifically designed for mid-market brands spending $50K-$500K annually on retail media.',
    },
    {
      url: 'https://www.adexchanger.com/retail-media/walmart-connect-api-2026/example/',
      title: 'Walmart Connect Opens API to Third-Party DSPs',
      published_date: '2026-02-27T14:30:00Z',
      snippet:
        "Walmart Connect is opening its retail media platform to third-party demand-side platforms through a new API integration program, giving advertisers more flexibility in how they access and activate Walmart's first-party shopper data.",
    },
    {
      url: 'https://www.emarketer.com/content/walmart-connect-q4-2025/example/',
      title: 'Walmart Connect Q4 2025 Revenue Analysis',
      published_date: '2026-02-26T11:00:00Z',
      snippet:
        "Walmart Connect's advertising revenue grew an estimated 28% year-over-year in Q4 2025, analysts say, outpacing the broader retail media market's 19% growth rate and narrowing the gap with Amazon Advertising.",
    },
    {
      url: 'https://www.marketingweek.com/walmart-connect-video-ads/example/',
      title: 'Walmart Connect Adds Video to In-Store Screens',
      published_date: '2026-02-25T16:00:00Z',
      snippet:
        'Walmart Connect is rolling out video ad formats across its network of 170,000 in-store digital screens, adding premium video inventory to a retail media portfolio that previously focused primarily on static display ads.',
    },
    {
      url: 'https://www.linkedin.com/news/walmart-connect-hire/example/',
      title: 'Walmart Connect Poaches Amazon Advertising Exec',
      published_date: '2026-02-24T08:00:00Z',
      snippet:
        "Walmart Connect has hired a former Amazon Advertising VP as its new Head of Advertiser Solutions, signaling the company's intent to accelerate its retail media platform capabilities with talent from the market leader.",
    },
  ],
  tool_trace: [
    {
      tool_name: 'search_company_news',
      input: {
        company: 'Walmart Connect',
        time_range: '7d',
      },
      output_summary:
        'Returned 12 articles about Walmart Connect from the past 7 days. Top topics: self-serve platform expansion (4 articles), API integration program (3 articles), Q4 2025 earnings commentary (2 articles), executive hiring (2 articles), in-store video ads (1 article).',
      latency_ms: 1243,
      timestamp: '2026-03-01T11:59:45Z',
    },
    {
      tool_name: 'search_news',
      input: {
        query: 'Walmart Connect retail media',
        time_range: '7d',
        num_results: 10,
      },
      output_summary:
        'Returned 10 articles covering Walmart Connect in the retail media context. 6 articles overlapped with company_news results; 4 new articles added including analyst revenue estimate and competitive positioning piece.',
      latency_ms: 987,
      timestamp: '2026-03-01T11:59:47Z',
    },
    {
      tool_name: 'search_news',
      input: {
        query: 'retail media network competition Amazon Criteo 2026',
        time_range: '7d',
        num_results: 10,
      },
      output_summary:
        'Returned 10 articles on retail media competitive landscape. Used for context on competitive positioning and risk assessment. No additional Walmart Connect signals found beyond what was already captured.',
      latency_ms: 1102,
      timestamp: '2026-03-01T11:59:49Z',
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
