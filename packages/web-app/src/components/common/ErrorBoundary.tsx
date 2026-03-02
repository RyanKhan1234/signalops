/**
 * ErrorBoundary — React error boundary for wrapping major digest sections.
 * Catches unexpected render errors and shows a user-friendly fallback.
 */

import { Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  /** Optional section name displayed in the fallback UI */
  sectionName?: string;
}

interface State {
  hasError: boolean;
  errorMessage: string;
}

/**
 * React class component error boundary.
 * Wrap major sections with this to prevent the whole app from crashing.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, errorMessage: '' };
  }

  static getDerivedStateFromError(error: unknown): State {
    return {
      hasError: true,
      errorMessage: error instanceof Error ? error.message : 'Unknown error',
    };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // In production, this would send to an error monitoring service
    console.error('[ErrorBoundary] Caught error:', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, errorMessage: '' });
  };

  render() {
    if (this.state.hasError) {
      const section = this.props.sectionName ?? 'This section';
      return (
        <div
          className="rounded-lg border border-red-200 bg-red-50 p-4"
          role="alert"
        >
          <p className="text-sm font-medium text-red-800">
            {section} failed to render
          </p>
          <p className="mt-1 text-xs text-red-600">{this.state.errorMessage}</p>
          <button
            onClick={this.handleReset}
            className="mt-2 text-xs font-medium text-red-800 underline hover:text-red-900"
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
