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

// Mock environment variables (loaded from vite.config.js test.env)
global.import = {
  meta: {
    env: {
      VITE_API_BASE_URL: process.env.VITE_API_BASE_URL,
      VITE_API_TIMEOUT_MS: process.env.VITE_API_TIMEOUT_MS,
    }
  }
};
