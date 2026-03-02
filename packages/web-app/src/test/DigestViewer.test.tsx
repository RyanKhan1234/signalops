/**
 * Tests for the DigestViewer component (integration test across all sections).
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DigestViewer } from '../components/digest/DigestViewer';
import { MOCK_DIGEST_RESPONSE } from '../mocks/mockDigestResponse';

describe('DigestViewer', () => {
  it('renders the executive summary section', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    expect(screen.getByText('Executive Summary')).toBeInTheDocument();
    expect(
      screen.getByText(MOCK_DIGEST_RESPONSE.executive_summary)
    ).toBeInTheDocument();
  });

  it('renders the key signals section heading', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    expect(screen.getByText('Key Signals')).toBeInTheDocument();
    // Check count badge appears at least once (may appear multiple times as '5' across sections)
    const countBadges = screen.getAllByText(String(MOCK_DIGEST_RESPONSE.key_signals.length));
    expect(countBadges.length).toBeGreaterThanOrEqual(1);
  });

  it('renders each key signal text', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    for (const signal of MOCK_DIGEST_RESPONSE.key_signals) {
      expect(screen.getByText(signal.signal)).toBeInTheDocument();
    }
  });

  it('renders the risks section', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    expect(screen.getByText('Risks')).toBeInTheDocument();
    for (const risk of MOCK_DIGEST_RESPONSE.risks) {
      expect(screen.getByText(risk.description)).toBeInTheDocument();
    }
  });

  it('renders the opportunities section', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    expect(screen.getByText('Opportunities')).toBeInTheDocument();
    for (const opp of MOCK_DIGEST_RESPONSE.opportunities) {
      expect(screen.getByText(opp.description)).toBeInTheDocument();
    }
  });

  it('renders the action items section with prioritized items', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    expect(screen.getByText('Action Items')).toBeInTheDocument();
    for (const item of MOCK_DIGEST_RESPONSE.action_items) {
      expect(screen.getByText(item.action)).toBeInTheDocument();
    }
  });

  it('renders the sources section with external links', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    expect(screen.getByText('Sources')).toBeInTheDocument();
    // Check that source titles appear in the document (they render as links)
    for (const source of MOCK_DIGEST_RESPONSE.sources) {
      // Use getByText which will match any element containing the title
      const titleEls = screen.getAllByText(source.title);
      expect(titleEls.length).toBeGreaterThan(0);
    }
    // Check that at least one link has target="_blank"
    const externalLinks = screen.getAllByRole('link');
    const hasExternalLink = externalLinks.some(
      (link) => link.getAttribute('target') === '_blank'
    );
    expect(hasExternalLink).toBe(true);
  });

  it('renders the tool trace section', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    expect(screen.getByText('Tool Trace')).toBeInTheDocument();
  });

  it('renders tool names in the tool trace', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    for (const entry of MOCK_DIGEST_RESPONSE.tool_trace) {
      expect(screen.getAllByText(entry.tool_name).length).toBeGreaterThan(0);
    }
  });

  it('renders the report ID somewhere in the document', () => {
    render(<DigestViewer digest={MOCK_DIGEST_RESPONSE} />);
    // report_id appears in executive summary metadata and tool trace panel
    const reportIdEls = screen.getAllByText(MOCK_DIGEST_RESPONSE.report_id);
    expect(reportIdEls.length).toBeGreaterThanOrEqual(1);
  });
});
