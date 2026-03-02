/**
 * Badge component for displaying severity, relevance, priority, and confidence labels.
 * Consistent color coding across all digest sections.
 */

import type { RelevanceLevel, SeverityLevel, ConfidenceLevel, PriorityLevel } from '../../types/digest';

type BadgeVariant = RelevanceLevel | SeverityLevel | ConfidenceLevel | PriorityLevel;

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  // Severity / Relevance / Confidence shared levels
  high: 'bg-red-100 text-red-800 ring-1 ring-red-200',
  medium: 'bg-yellow-100 text-yellow-800 ring-1 ring-yellow-200',
  low: 'bg-green-100 text-green-800 ring-1 ring-green-200',
  // Priority levels
  P0: 'bg-red-100 text-red-800 ring-1 ring-red-200',
  P1: 'bg-orange-100 text-orange-800 ring-1 ring-orange-200',
  P2: 'bg-blue-100 text-blue-800 ring-1 ring-blue-200',
};

const VARIANT_LABELS: Record<BadgeVariant, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  P0: 'P0 — Immediate',
  P1: 'P1 — High',
  P2: 'P2 — Medium',
};

interface BadgeProps {
  /** The badge value to display */
  variant: BadgeVariant;
  /** Optional prefix label (e.g. "Severity", "Relevance") */
  prefix?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Renders a colored badge label for severity, relevance, priority, or confidence levels.
 */
export function Badge({ variant, prefix, className = '' }: BadgeProps) {
  const colorClasses = VARIANT_CLASSES[variant] ?? 'bg-gray-100 text-gray-800';
  const label = VARIANT_LABELS[variant] ?? variant;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${colorClasses} ${className}`}
      aria-label={prefix ? `${prefix}: ${label}` : label}
    >
      {prefix && <span className="text-xs opacity-70">{prefix}:</span>}
      {label}
    </span>
  );
}
