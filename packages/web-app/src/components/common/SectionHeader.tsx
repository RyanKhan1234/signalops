/**
 * SectionHeader — consistent heading style for each digest section.
 */

interface SectionHeaderProps {
  title: string;
  count?: number;
  description?: string;
}

/**
 * Renders a consistent section heading with optional item count and description.
 */
export function SectionHeader({ title, count, description }: SectionHeaderProps) {
  return (
    <div className="mb-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        {count !== undefined && (
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
            {count}
          </span>
        )}
      </div>
      {description && (
        <p className="mt-1 text-sm text-gray-500">{description}</p>
      )}
    </div>
  );
}
