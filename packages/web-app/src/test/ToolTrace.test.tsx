/**
 * Tests for the ToolTrace component.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToolTrace } from '../components/debug/ToolTrace';
import type { ToolTraceEntry } from '../types/digest';

const SAMPLE_ENTRIES: ToolTraceEntry[] = [
  {
    tool_name: 'search_company_news',
    input: { company: 'OpenAI', time_range: '7d' },
    output_summary: 'Returned 12 articles about OpenAI.',
    latency_ms: 1243,
    timestamp: '2026-03-01T11:59:45Z',
  },
  {
    tool_name: 'search_news',
    input: { query: 'OpenAI AI research', time_range: '7d' },
    output_summary: 'Returned 10 articles.',
    latency_ms: 987,
    timestamp: '2026-03-01T11:59:47Z',
  },
];

describe('ToolTrace', () => {
  it('renders the section heading', () => {
    render(<ToolTrace toolTrace={SAMPLE_ENTRIES} reportId="rpt_test_123" />);
    expect(screen.getByText('Tool Trace')).toBeInTheDocument();
  });

  it('renders tool names for all entries', () => {
    render(<ToolTrace toolTrace={SAMPLE_ENTRIES} reportId="rpt_test_123" />);
    expect(screen.getAllByText('search_company_news').length).toBeGreaterThan(0);
    expect(screen.getAllByText('search_news').length).toBeGreaterThan(0);
  });

  it('displays the report ID', () => {
    render(<ToolTrace toolTrace={SAMPLE_ENTRIES} reportId="rpt_test_123" />);
    expect(screen.getByText('rpt_test_123')).toBeInTheDocument();
  });

  it('displays latency for each entry', () => {
    render(<ToolTrace toolTrace={SAMPLE_ENTRIES} reportId="rpt_test_123" />);
    // 1243ms and 987ms
    expect(screen.getAllByText(/1,243ms/)).toHaveLength(1);
    expect(screen.getAllByText(/987ms/)).toHaveLength(1);
  });

  it('shows total latency', () => {
    render(<ToolTrace toolTrace={SAMPLE_ENTRIES} reportId="rpt_test_123" />);
    // 1243 + 987 = 2230
    expect(screen.getByText(/2,230ms/)).toBeInTheDocument();
  });

  it('expands an entry when clicked to show input and output', async () => {
    render(<ToolTrace toolTrace={SAMPLE_ENTRIES} reportId="rpt_test_123" />);
    const firstButton = screen.getAllByRole('button')[0];
    expect(firstButton).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(firstButton);
    expect(firstButton).toHaveAttribute('aria-expanded', 'true');

    // Should show the output summary text
    expect(screen.getByText('Returned 12 articles about OpenAI.')).toBeInTheDocument();
  });

  it('renders empty state when toolTrace is empty', () => {
    render(<ToolTrace toolTrace={[]} reportId="rpt_test_123" />);
    expect(
      screen.getByText('No tool calls recorded for this digest.')
    ).toBeInTheDocument();
  });

  it('shows correct tool call count in the section header badge', () => {
    render(<ToolTrace toolTrace={SAMPLE_ENTRIES} reportId="rpt_test_123" />);
    // The count badge in SectionHeader shows SAMPLE_ENTRIES.length = 2
    // Also appears as "Tool calls: 2" in the metadata row
    // Use getAllByText to check at least one occurrence
    const countMatches = screen.getAllByText(String(SAMPLE_ENTRIES.length));
    expect(countMatches.length).toBeGreaterThanOrEqual(1);
  });
});
