/**
 * PanelCard — white card wrapper with an id for anchor navigation.
 * Each dashboard section is wrapped in a PanelCard so the sidebar
 * nav links can scroll directly to the section.
 */

interface PanelCardProps {
  id: string;
  children: React.ReactNode;
}

/**
 * Renders a white card section with scroll-margin for fixed header offset.
 */
export function PanelCard({ id, children }: PanelCardProps) {
  return (
    <section id={id} className="scroll-mt-6">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {children}
      </div>
    </section>
  );
}
