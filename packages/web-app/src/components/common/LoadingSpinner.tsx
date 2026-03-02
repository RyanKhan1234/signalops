/**
 * LoadingSpinner — animated loading indicator for digest generation.
 */

interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

const SIZE_CLASSES = {
  sm: 'h-4 w-4 border-2',
  md: 'h-8 w-8 border-2',
  lg: 'h-12 w-12 border-4',
};

/**
 * Accessible animated spinner with optional label text.
 */
export function LoadingSpinner({
  label = 'Generating digest...',
  size = 'md',
}: LoadingSpinnerProps) {
  return (
    <div
      className="flex items-center gap-3"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div
        className={`${SIZE_CLASSES[size]} animate-spin rounded-full border-brand-200 border-t-brand-600`}
      />
      {label && (
        <span className="text-sm text-gray-500">{label}</span>
      )}
    </div>
  );
}
