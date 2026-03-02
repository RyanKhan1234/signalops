/**
 * Card component — standard bordered container for digest section items.
 */

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

/** A clean, bordered card container for digest content blocks. */
export function Card({ children, className = '' }: CardProps) {
  return (
    <div
      className={`rounded-lg border border-gray-200 bg-white p-4 shadow-sm ${className}`}
    >
      {children}
    </div>
  );
}
