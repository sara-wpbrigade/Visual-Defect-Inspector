import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// jsdom does not implement object URLs; the preview only needs a stable string.
URL.createObjectURL = vi.fn(() => 'blob:preview');
URL.revokeObjectURL = vi.fn();
