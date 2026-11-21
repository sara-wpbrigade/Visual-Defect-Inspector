import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App.jsx';
import { ErrorBoundary } from './components/ErrorBoundary.jsx';
import './index.css';

const THEME_KEY = 'vdi-theme';

/** Set data-theme on <html> early to avoid a flash of the wrong theme. */
function applyInitialTheme() {
  let stored;
  try {
    stored = window.localStorage.getItem(THEME_KEY);
  } catch {
    stored = null;
  }
  const systemPrefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
  const theme =
    stored === 'light' || stored === 'dark' ? stored : systemPrefersDark ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
}

applyInitialTheme();

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root is missing from index.html.');
}

createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
