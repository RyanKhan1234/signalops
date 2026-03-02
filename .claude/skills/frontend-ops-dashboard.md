# Ops Dashboard Frontend Patterns

## Design Direction
- Professional, utilitarian ops tool aesthetic — NOT a consumer app
- Clean typographic hierarchy, data-dense but readable
- Light theme with strategic color coding for severity/priority
- Desktop-optimized, responsive as secondary concern
- Think Bloomberg Terminal meets modern SaaS — information density with clarity

## Component Patterns
- Digest sections as distinct card-based regions with subtle borders
- Collapsible debug/trace panels (default collapsed)
- Severity badges: red (high), amber (medium), green (low)
- Priority badges: P0 (red filled), P1 (amber filled), P2 (blue outlined)
- Source links always open in new tab with external link icon
- Loading skeletons over spinners for section-level loading
- Streaming text animation for executive summary during generation

## Typography
- Use a monospace font for debug/trace data (JetBrains Mono or similar)
- Use a clean sans-serif for body content (system font stack is fine for ops tools)
- Clear size hierarchy: section headers > signal text > metadata > timestamps

## Color System
- Background: white/near-white (#FAFAFA)
- Cards: white with subtle border (#E5E7EB)
- Primary accent: deep blue (#1E40AF) for interactive elements
- Severity red: #DC2626, amber: #D97706, green: #059669
- Priority P0: #DC2626, P1: #D97706, P2: #3B82F6
- Muted text: #6B7280 for timestamps and metadata

## Tech Constraints
- React 18+ with TypeScript strict mode
- Tailwind CSS (no component libraries except shadcn/ui if needed)
- Vite for builds
- All state management via React hooks (no Redux/Zustand for v1)
- Fetch API for HTTP calls (no axios dependency needed)
