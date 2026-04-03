/**
 * UserContextSettings — freeform context editor that personalizes the research pipeline.
 */

import { useState, useEffect, useCallback } from 'react';
import { getUserProfile, saveUserProfile } from '../../services/api';

const USER_ID = 'default';

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

export function UserContextSettings({ onBack }: { onBack: () => void }) {
  const [context, setContext] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const profile = await getUserProfile(USER_ID);
        if (!cancelled && profile) {
          setContext(profile.context);
          setDisplayName(profile.display_name ?? '');
        }
      } catch {
        // No profile yet — that's fine
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleSave = useCallback(async () => {
    setSaveStatus('saving');
    try {
      await saveUserProfile(USER_ID, {
        display_name: displayName || null,
        context,
      });
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch {
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  }, [context, displayName]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-5">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="flex items-center justify-center rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500"
            aria-label="Back to chat"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">My Context</h2>
            <p className="text-sm text-gray-500">
              This shapes how SignalOps researches and what it highlights for you
            </p>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Display name */}
          <div>
            <label htmlFor="display-name" className="block text-sm font-medium text-gray-700 mb-1.5">
              Name
            </label>
            <input
              id="display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="What should SignalOps call you?"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          {/* Context */}
          <div>
            <label htmlFor="user-context" className="block text-sm font-medium text-gray-700 mb-1.5">
              About you
            </label>
            <p className="text-xs text-gray-500 mb-2">
              Tell SignalOps about yourself — what you're working on, what you care about,
              what you're trying to figure out. There's no format; just write naturally.
            </p>
            <textarea
              id="user-context"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              rows={12}
              placeholder={
                "Examples of things you might write:\n\n" +
                "• I'm a journalism student interested in how AI is changing newsrooms\n" +
                "• I run a small landscaping business in Austin and want to stay on top of industry trends\n" +
                "• I'm deep into Formula 1 — I track team strategy, driver contracts, and regulation changes\n" +
                "• I'm exploring a career switch from finance to product management in tech"
              }
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 leading-relaxed resize-y focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
            <p className="mt-1.5 text-xs text-gray-400">
              {context.length.toLocaleString()} / 10,000 characters
            </p>
          </div>

          {/* How it works */}
          <div className="rounded-xl border border-gray-100 bg-gray-50 p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">How this works</h3>
            <ul className="space-y-1.5 text-xs text-gray-500 leading-relaxed">
              <li>Your context is sent to the research agent with every query</li>
              <li>The agent uses it to decide which tools to call and what search queries to run</li>
              <li>Findings, concerns, and next steps are tailored to your background and interests</li>
              <li>If you leave this blank, research works the same as before — just not personalized</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Footer with save button */}
      <div className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center justify-end gap-3">
          {saveStatus === 'saved' && (
            <span className="text-sm text-green-600">Saved</span>
          )}
          {saveStatus === 'error' && (
            <span className="text-sm text-red-600">Failed to save — try again</span>
          )}
          <button
            type="button"
            onClick={handleSave}
            disabled={saveStatus === 'saving'}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saveStatus === 'saving' ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
