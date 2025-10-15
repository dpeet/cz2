/**
 * API Service Tests - Red Phase (TDD)
 *
 * These tests encode the contract for the Python cz2 backend API migration.
 * All tests should FAIL initially until implementation (Green phase).
 *
 * Contract Requirements (from API_COMMANDS.md):
 * - systemMode(mode, { all }) -> POST /system/mode with { mode, all }
 * - systemFan(fan) -> POST /system/fan with { fan } (maps "Auto"/"On")
 * - setZoneTemperature(zoneId, { mode, temp }) -> POST /zones/{id}/temperature
 * - setZoneHold(zoneId, hold) -> POST /zones/{id}/hold with { hold, temp }
 * - requestUpdate() -> POST /update with empty body
 * - All functions respect VITE_API_BASE_URL and VITE_API_TIMEOUT_MS
 * - Errors bubble up as rejected promises
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import {
  systemMode,
  systemFan,
  setZoneTemperature,
  setZoneHold,
  requestUpdate,
  resetApiClient,
} from '../apiService';

// Mock axios
vi.mock('axios');

describe('API Service - Environment Configuration', () => {
  beforeEach(() => {
    resetApiClient();
    vi.clearAllMocks();
    resetApiClient();
  });

  it('should use VITE_API_BASE_URL when set', async () => {
    // Test that base URL is sourced from import.meta.env.VITE_API_BASE_URL
    // Expected: API calls use configured base URL
    const mockCreate = vi.fn().mockReturnValue({
      post: vi.fn().mockResolvedValue({ data: {} }),
    });
    axios.create = mockCreate;

    // Trigger client creation by calling a function
    await requestUpdate().catch(() => {});

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        baseURL: 'http://localhost:8000',
      })
    );
  });

  it('should fallback to window.location.origin if VITE_API_BASE_URL unset', async () => {
    // Test fallback behavior when env var is not set
    // Expected: Uses window.location.origin as base URL
    const originalEnv = import.meta.env.VITE_API_BASE_URL;
    delete import.meta.env.VITE_API_BASE_URL;

    const mockCreate = vi.fn().mockReturnValue({
      post: vi.fn().mockResolvedValue({ data: {} }),
    });
    axios.create = mockCreate;

    // Trigger client creation by calling a function
    await requestUpdate().catch(() => {});

    // Restore
    import.meta.env.VITE_API_BASE_URL = originalEnv;

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        baseURL: window.location.origin,
      })
    );
  });

  it('should use VITE_API_TIMEOUT_MS from environment', async () => {
    // Test that timeout is sourced from configured env value
    // Expected: timeout matches configured VITE_API_TIMEOUT_MS value
    const mockCreate = vi.fn().mockReturnValue({
      post: vi.fn().mockResolvedValue({ data: {} }),
    });
    axios.create = mockCreate;

    // Trigger client creation by calling a function
    await requestUpdate().catch(() => {});

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        timeout: Number(process.env.VITE_API_TIMEOUT_MS),
      })
    );
  });
});

describe('API Service - systemMode()', () => {
  let mockAxiosInstance;

  beforeEach(() => {
    resetApiClient();
    vi.clearAllMocks();
    resetApiClient();
    mockAxiosInstance = {
      post: vi.fn(),
    };
    axios.create = vi.fn().mockReturnValue(mockAxiosInstance);
  });

  it('should send POST to /system/mode with mode and all=true', async () => {
    // Requirement: systemMode(mode, { all }) sends POST /system/mode
    // with JSON { mode, all } and returns parsed response
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: { system_mode: 'Heat' },
        meta: { connected: true },
        message: 'System mode set to Heat',
      },
    });

    const result = await systemMode('Heat', { all: true });

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/system/mode', {
      mode: 'Heat',
      all: true,
    });
    expect(result).toEqual({
      status: { system_mode: 'Heat' },
      meta: { connected: true },
      message: 'System mode set to Heat',
    });
  });

  it('should send POST to /system/mode with mode only (no all param)', async () => {
    // Requirement: When { all } is not provided, only send mode
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: { system_mode: 'Cool' },
        meta: { connected: true },
      },
    });

    const result = await systemMode('Cool');

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/system/mode', {
      mode: 'Cool',
    });
    expect(result).toBeDefined();
  });

  it('should handle all=false correctly', async () => {
    // Requirement: all=false should disable all-call mode
    mockAxiosInstance.post.mockResolvedValue({
      data: { status: {}, meta: {} },
    });

    await systemMode('Auto', { all: false });

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/system/mode', {
      mode: 'Auto',
      all: false,
    });
  });
});

describe('API Service - systemFan()', () => {
  let mockAxiosInstance;

  beforeEach(() => {
    resetApiClient();
    vi.clearAllMocks();
    resetApiClient();
    mockAxiosInstance = {
      post: vi.fn(),
    };
    axios.create = vi.fn().mockReturnValue(mockAxiosInstance);
  });

  it('should send POST to /system/fan with fan="Auto"', async () => {
    // Requirement: systemFan(fan) sends POST /system/fan with { fan }
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: { fan_mode: 'Auto' },
        meta: { connected: true },
      },
    });

    const result = await systemFan('Auto');

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/system/fan', {
      fan: 'Auto',
    });
    expect(result.status.fan_mode).toBe('Auto');
  });

  it('should send POST to /system/fan with fan="On" (maps always_on)', async () => {
    // Requirement: Correctly map "always_on" vs "auto" (backend uses "On")
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: { fan_mode: 'On' },
        meta: { connected: true },
      },
    });

    const result = await systemFan('On');

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/system/fan', {
      fan: 'On',
    });
    expect(result.status.fan_mode).toBe('On');
  });
});

describe('API Service - setZoneTemperature()', () => {
  let mockAxiosInstance;

  beforeEach(() => {
    resetApiClient();
    vi.clearAllMocks();
    mockAxiosInstance = {
      post: vi.fn(),
    };
    axios.create = vi.fn().mockReturnValue(mockAxiosInstance);
  });

  it('should POST to /zones/{id}/temperature with heat setpoint', async () => {
    // Requirement: setZoneTemperature(zoneId, { mode, temp }) calls
    // POST /zones/{zoneId}/temperature with { heat: temp } when mode='heat'
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: { zones: [{ heat_setpoint: 68 }] },
        meta: { connected: true },
      },
    });

    const result = await setZoneTemperature(1, { mode: 'heat', temp: 68 });

    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/zones/1/temperature',
      {
        heat: 68,
      }
    );
    expect(result).toBeDefined();
  });

  it('should POST to /zones/{id}/temperature with cool setpoint', async () => {
    // Requirement: { cool: temp } when mode='cool'
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: { zones: [{ cool_setpoint: 75 }] },
        meta: { connected: true },
      },
    });

    const result = await setZoneTemperature(2, { mode: 'cool', temp: 75 });

    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/zones/2/temperature',
      {
        cool: 75,
      }
    );
    expect(result).toBeDefined();
  });

  it('should include temp and hold flags when provided', async () => {
    // Requirement: Include temp/hold flags per API_COMMANDS.md
    mockAxiosInstance.post.mockResolvedValue({
      data: { status: {}, meta: {} },
    });

    await setZoneTemperature(1, {
      mode: 'heat',
      temp: 70,
      tempFlag: true,
      hold: false,
    });

    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/zones/1/temperature',
      expect.objectContaining({
        heat: 70,
      })
    );
  });
});

describe('API Service - setZoneHold()', () => {
  let mockAxiosInstance;

  beforeEach(() => {
    resetApiClient();
    vi.clearAllMocks();
    mockAxiosInstance = {
      post: vi.fn(),
    };
    axios.create = vi.fn().mockReturnValue(mockAxiosInstance);
  });

  it('should POST to /zones/{id}/hold with hold=true, temp=true', async () => {
    // Requirement: setZoneHold(zoneId, hold) posts to /zones/{zoneId}/hold
    // with { hold: true/false, temp: true }
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: { zones: [{ hold: 1 }] },
        meta: { connected: true },
      },
    });

    const result = await setZoneHold(1, true);

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/zones/1/hold', {
      hold: true,
      temp: true,
    });
    expect(result).toBeDefined();
  });

  it('should POST to /zones/{id}/hold with hold=false, temp=true', async () => {
    // Requirement: Support disabling hold
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: { zones: [{ hold: 0 }] },
        meta: { connected: true },
      },
    });

    await setZoneHold(2, false);

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/zones/2/hold', {
      hold: false,
      temp: true,
    });
  });

  it('should handle zoneId="all" by iterating cached status zones', async () => {
    // Requirement: When zoneId === "all", issue requests for each zone
    // in cached status
    const cachedStatus = {
      zones: [
        { temperature: 70 },
        { temperature: 68 },
        { temperature: 72 },
      ],
    };

    mockAxiosInstance.post.mockResolvedValue({
      data: { status: {}, meta: {} },
    });

    await setZoneHold('all', true, cachedStatus);

    expect(mockAxiosInstance.post).toHaveBeenCalledTimes(3);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/zones/1/hold', {
      hold: true,
      temp: true,
    });
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/zones/2/hold', {
      hold: true,
      temp: true,
    });
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/zones/3/hold', {
      hold: true,
      temp: true,
    });
  });

  it('should throw error when zoneId="all" but no cachedStatus provided', async () => {
    // Requirement: Need cached status to determine zone count for "all"
    await expect(setZoneHold('all', true)).rejects.toThrow();
  });
});

describe('API Service - requestUpdate()', () => {
  let mockAxiosInstance;

  beforeEach(() => {
    resetApiClient();
    vi.clearAllMocks();
    mockAxiosInstance = {
      post: vi.fn(),
    };
    axios.create = vi.fn().mockReturnValue(mockAxiosInstance);
  });

  it('should POST to /update with empty body', async () => {
    // Requirement: requestUpdate() posts to /update with empty body
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: { system_mode: 'Heat' },
        meta: { connected: true },
      },
    });

    const result = await requestUpdate();

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/update', {});
    expect(result).toBeDefined();
  });
});

describe('API Service - Error Handling', () => {
  let mockAxiosInstance;

  beforeEach(() => {
    resetApiClient();
    vi.clearAllMocks();
    mockAxiosInstance = {
      post: vi.fn(),
    };
    axios.create = vi.fn().mockReturnValue(mockAxiosInstance);
  });

  it('should bubble up errors as rejected promises without swallowing', async () => {
    // Requirement: Errors should bubble up as rejected promises
    const networkError = new Error('Network Error');
    mockAxiosInstance.post.mockRejectedValue(networkError);

    await expect(systemMode('Heat')).rejects.toThrow('Network Error');
  });

  it('should propagate 422 validation errors from backend', async () => {
    // Requirement: Backend validation errors should reach caller
    const validationError = {
      response: {
        status: 422,
        data: { detail: 'Invalid mode' },
      },
    };
    mockAxiosInstance.post.mockRejectedValue(validationError);

    await expect(systemFan('InvalidMode')).rejects.toEqual(validationError);
  });

  it('should propagate 500 server errors from backend', async () => {
    // Requirement: Server errors should bubble up
    const serverError = {
      response: {
        status: 500,
        data: { detail: 'HVAC communication failure' },
      },
    };
    mockAxiosInstance.post.mockRejectedValue(serverError);

    await expect(requestUpdate()).rejects.toEqual(serverError);
  });
});

describe('API Service - Response Normalization', () => {
  let mockAxiosInstance;

  beforeEach(() => {
    resetApiClient();
    vi.clearAllMocks();
    mockAxiosInstance = {
      post: vi.fn(),
    };
    axios.create = vi.fn().mockReturnValue(mockAxiosInstance);
  });

  it('should handle { status, meta } response format', async () => {
    // Requirement: When backend returns { status, meta }, service should
    // normalize via json_response.js helper (if exists) or return as-is
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        status: {
          system_mode: 'Auto',
          zones: [{ temperature: 70 }],
        },
        meta: {
          connected: true,
          is_stale: false,
          source: 'writeback',
        },
      },
    });

    const result = await systemMode('Auto');

    expect(result).toHaveProperty('status');
    expect(result).toHaveProperty('meta');
    expect(result.meta.connected).toBe(true);
  });

  it('should handle flat status payload format', async () => {
    // Requirement: Support legacy flat status payload (clarify if needed)
    mockAxiosInstance.post.mockResolvedValue({
      data: {
        system_mode: 'Heat',
        fan_mode: 'Auto',
        zones: [],
      },
    });

    const result = await systemMode('Heat');

    expect(result).toHaveProperty('system_mode');
  });
});
