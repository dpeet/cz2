// Test setup file for Vitest
import { vi, expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

// Extend Vitest's expect with testing-library matchers
expect.extend(matchers);

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock environment variables
global.import = {
  meta: {
    env: {
      VITE_API_BASE_URL: 'http://localhost:8000',
      VITE_API_TIMEOUT_MS: '5000',
    }
  }
};
