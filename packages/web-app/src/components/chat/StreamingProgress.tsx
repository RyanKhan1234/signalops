/**
 * StreamingProgress — renders real-time pipeline progress during digest generation.
 *
 * Displays an animated timeline of events: intent detection, tool calls with
 * agent reasoning, article processing stages, and composition.
 */

import type { StreamEvent } from '../../types/digest';

interface StreamingProgressProps {
  events: StreamEvent[];
}

const STAGE_LABELS: Record<string, string> = {
  clustering: 'Clustering articles by theme',
  extracting_signals: 'Extracting key signals',
  identifying_risks: 'Identifying risks & opportunities',
  generating_actions: 'Generating action items',
  executive_summary: 'Composing executive summary',
};

function ToolIcon() {
  return (
    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

function BrainIcon() {
  return (
    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function renderEvent(event: StreamEvent, index: number) {
  const { event: type, data } = event;

  if (type === 'intent') {
    const intentLabels: Record<string, string> = {
      latest_news: 'Latest News',
      deep_dive: 'Deep Dive',
      risk_scan: 'Risk Scan',
      trend_watch: 'Trend Watch',
    };
    const label = intentLabels[data.intent_type as string] ?? data.intent_type;
    const entities = (data.entities as string[])?.join(', ') ?? '';
    return (
      <div key={index} className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
          <BrainIcon />
        </div>
        <div className="text-sm">
          <span className="font-medium text-gray-900">
            {label as string}
          </span>
          {entities && (
            <span className="text-gray-500"> — {entities}</span>
          )}
        </div>
      </div>
    );
  }

  if (type === 'tool_call') {
    const tool = data.tool as string;
    const args = data.arguments as Record<string, unknown>;
    const query = args?.query ?? args?.company ?? args?.url ?? '';
    return (
      <div key={index} className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-600">
          <ToolIcon />
        </div>
        <div className="text-sm">
          <span className="font-mono text-xs font-medium text-blue-700">
            {tool}
          </span>
          {query && (
            <span className="ml-1 text-gray-500">
              &ldquo;{String(query).slice(0, 80)}&rdquo;
            </span>
          )}
        </div>
      </div>
    );
  }

  if (type === 'tool_result') {
    const count = data.articles_found as number;
    const ms = data.latency_ms as number;
    return (
      <div key={index} className="flex items-start gap-2.5 pl-7">
        <div className="text-xs text-gray-400">
          {count > 0
            ? `${count} result${count !== 1 ? 's' : ''}`
            : 'no results'}
          {ms ? ` (${ms}ms)` : ''}
          {data.status === 'error' && (
            <span className="ml-1 text-red-500">failed</span>
          )}
        </div>
      </div>
    );
  }

  if (type === 'reasoning') {
    const step = data.step as string;
    return (
      <div key={index} className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-600">
          <BrainIcon />
        </div>
        <div className="text-sm italic text-gray-600">
          {step.length > 200 ? step.slice(0, 200) + '...' : step}
        </div>
      </div>
    );
  }

  if (type === 'processing') {
    const stage = data.stage as string;
    const label = STAGE_LABELS[stage] ?? stage;
    return (
      <div key={index} className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-green-100 text-green-600">
          <GearIcon />
        </div>
        <div className="text-sm text-gray-700">{label}</div>
      </div>
    );
  }

  if (type === 'composing') {
    const stage = data.stage as string;
    const label = STAGE_LABELS[stage] ?? stage;
    return (
      <div key={index} className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-purple-100 text-purple-600">
          <GearIcon />
        </div>
        <div className="text-sm text-gray-700">{label}</div>
      </div>
    );
  }

  return null;
}

export function StreamingProgress({ events }: StreamingProgressProps) {
  if (events.length === 0) return null;

  return (
    <div className="flex justify-start">
      <div className="w-full rounded-2xl rounded-tl-sm border border-gray-200 bg-white px-5 py-4 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100">
            <svg
              className="h-3.5 w-3.5 text-brand-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          </div>
          <span className="text-xs font-medium text-gray-500">Agent Researching</span>
          <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-green-400" />
        </div>
        <div className="flex flex-col gap-1.5">
          {events.map((event, i) => renderEvent(event, i))}
        </div>
      </div>
    </div>
  );
}
