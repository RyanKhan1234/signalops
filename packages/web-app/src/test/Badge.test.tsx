/**
 * Tests for the Badge component.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from '../components/common/Badge';

describe('Badge', () => {
  it('renders high severity with red styling', () => {
    render(<Badge variant="high" />);
    const badge = screen.getByText('High');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('red');
  });

  it('renders medium severity with yellow styling', () => {
    render(<Badge variant="medium" />);
    const badge = screen.getByText('Medium');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('yellow');
  });

  it('renders low severity with green styling', () => {
    render(<Badge variant="low" />);
    const badge = screen.getByText('Low');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('green');
  });

  it('renders P0 priority badge', () => {
    render(<Badge variant="P0" />);
    expect(screen.getByText('P0 — Immediate')).toBeInTheDocument();
  });

  it('renders P1 priority badge', () => {
    render(<Badge variant="P1" />);
    expect(screen.getByText('P1 — High')).toBeInTheDocument();
  });

  it('renders P2 priority badge', () => {
    render(<Badge variant="P2" />);
    expect(screen.getByText('P2 — Medium')).toBeInTheDocument();
  });

  it('renders with prefix label', () => {
    render(<Badge variant="high" prefix="Severity" />);
    const badge = screen.getByLabelText('Severity: High');
    expect(badge).toBeInTheDocument();
  });

  it('applies additional className', () => {
    const { container } = render(<Badge variant="high" className="flex-shrink-0" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain('flex-shrink-0');
  });
});
