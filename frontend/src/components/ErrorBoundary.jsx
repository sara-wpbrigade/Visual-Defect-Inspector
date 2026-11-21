/** Catches render errors and shows a friendly recovery card. */

import { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
    this.handleReload = this.handleReload.bind(this);
    this.handleDismiss = this.handleDismiss.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Intentionally use the module logger, not console.log.
    // Replace with your logger if you add one later.
    if (typeof window !== 'undefined' && window.reportError) {
      window.reportError(error);
    }
    if (info?.componentStack) {
      console.error('Error boundary caught:', error, info.componentStack);
    }
  }

  handleReload() {
    window.location.reload();
  }

  handleDismiss() {
    this.setState({ error: null });
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <div className="app">
        <div className="card error-card" role="alert" style={{ marginTop: '48px' }}>
          <p className="step-label">Unexpected error</p>
          <h2>The interface hit an error</h2>
          <p className="error-message">
            {this.state.error?.message ?? 'An unknown error occurred.'}
          </p>
          <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
            <button type="button" className="button primary" onClick={this.handleReload}>
              Reload app
            </button>
            <button type="button" className="button secondary" onClick={this.handleDismiss}>
              Dismiss
            </button>
          </div>
        </div>
      </div>
    );
  }
}
