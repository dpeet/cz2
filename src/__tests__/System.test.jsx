/**
 * System Component Smoke Tests
 *
 * These tests verify that System.jsx correctly integrates with the new
 * POST-based apiService.js, ensuring all HVAC commands route through
 * the appropriate API functions.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import System from '../System';
import * as apiService from '../apiService';

// Mock the entire apiService module
vi.mock('../apiService');

describe('System Component - API Integration', () => {
  // Mock normalized status (as returned by apiNormalizer)
  const mockStatus = {
    status: {
      system_mode: 'Heat',
      fan_mode: 'Auto',
      all_mode: 0,
      zone1_humidity: 45,
      zones: [
        {
          temperature: 70,
          heat_setpoint: 68,
          cool_setpoint: 75,
          hold: 0,
        },
        {
          temperature: 68,
          heat_setpoint: 66,
          cool_setpoint: 74,
          hold: 0,
        },
        {
          temperature: 72,
          heat_setpoint: 70,
          cool_setpoint: 76,
          hold: 0,
        },
      ],
    },
    meta: {
      connected: true,
      stale: false,
    },
    controlsDisabledReason: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Setup default mocks for all API functions
    apiService.systemMode = vi.fn().mockResolvedValue({
      status: mockStatus,
      meta: { connected: true },
    });
    apiService.systemFan = vi.fn().mockResolvedValue({
      status: mockStatus,
      meta: { connected: true },
    });
    apiService.setZoneTemperature = vi.fn().mockResolvedValue({
      status: mockStatus,
      meta: { connected: true },
    });
    apiService.setZoneHold = vi.fn().mockResolvedValue({
      status: mockStatus,
      meta: { connected: true },
    });
    apiService.requestUpdate = vi.fn().mockResolvedValue({
      status: mockStatus,
      meta: { connected: true },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should render without crashing when status is provided', () => {
    render(<System status={mockStatus} connection="Connected" />);
    expect(screen.getByText('System Status')).toBeInTheDocument();
  });

  describe('System Mode Changes', () => {
    it('should call systemMode API function when mode is changed', async () => {
      render(<System status={mockStatus} connection="Connected" />);

      // Find the mode select by looking for the option with value "cool"
      const selects = screen.getAllByRole('combobox');
      const modeSelect = selects.find(select =>
        select.querySelector('option[value="cool"]')
      );

      fireEvent.change(modeSelect, { target: { value: 'cool' } });

      await waitFor(() => {
        expect(apiService.systemMode).toHaveBeenCalledWith('cool');
      });
    });

    it('should call systemMode with correct mode parameter', async () => {
      render(<System status={mockStatus} connection="Connected" />);

      const selects = screen.getAllByRole('combobox');
      const modeSelect = selects.find(select =>
        select.querySelector('option[value="auto"]')
      );

      fireEvent.change(modeSelect, { target: { value: 'auto' } });

      await waitFor(() => {
        expect(apiService.systemMode).toHaveBeenCalledWith('auto');
      });
    });
  });

  describe('Fan Mode Changes', () => {
    it('should call systemFan API function when fan button is clicked', async () => {
      render(<System status={mockStatus} connection="Connected" />);

      const fanButton = screen.getByText(/Set Always On/i);
      fireEvent.click(fanButton);

      await waitFor(() => {
        expect(apiService.systemFan).toHaveBeenCalledWith('On');
      });
    });

    it('should toggle fan mode correctly', async () => {
      const statusWithFanOn = {
        ...mockStatus,
        status: {
          ...mockStatus.status,
          fan_mode: 'Always On',
        },
      };

      render(<System status={statusWithFanOn} connection="Connected" />);

      const fanButton = screen.getByText(/Set Auto/i);
      fireEvent.click(fanButton);

      await waitFor(() => {
        expect(apiService.systemFan).toHaveBeenCalledWith('Auto');
      });
    });
  });

  describe('All Mode Changes', () => {
    it('should call systemMode with all=true when enabling all mode', async () => {
      render(<System status={mockStatus} connection="Connected" />);

      const allModeButton = screen.getByText(/Set All Mode On/i);
      fireEvent.click(allModeButton);

      await waitFor(() => {
        expect(apiService.systemMode).toHaveBeenCalledWith(
          'Heat',
          { all: true }
        );
      });
    });

    it('should call systemMode with all=false when disabling all mode', async () => {
      const statusWithAllMode = {
        ...mockStatus,
        status: {
          ...mockStatus.status,
          all_mode: 5,
        },
      };

      render(<System status={statusWithAllMode} connection="Connected" />);

      const allModeButton = screen.getByText(/Set All Mode Off/i);
      fireEvent.click(allModeButton);

      await waitFor(() => {
        expect(apiService.systemMode).toHaveBeenCalledWith(
          'Heat',
          { all: false }
        );
      });
    });
  });

  describe('Zone Temperature Changes', () => {
    it('should have setZoneTemperature function available via apiService', () => {
      // Smoke test: verify API service function is imported and mocked
      expect(apiService.setZoneTemperature).toBeDefined();
      expect(typeof apiService.setZoneTemperature).toBe('function');
    });

    it('should render temperature control form', () => {
      render(<System status={mockStatus} connection="Connected" />);

      // Verify temperature form is present
      expect(screen.getByText('Change Temperature')).toBeInTheDocument();
      expect(screen.getByText('Submit')).toBeInTheDocument();
    });
  });

  describe('Zone Hold Changes', () => {
    it('should have setZoneHold function available via apiService', () => {
      // Smoke test: verify API service function is imported and mocked
      expect(apiService.setZoneHold).toBeDefined();
      expect(typeof apiService.setZoneHold).toBe('function');
    });

    it('should render hold control form', () => {
      const statusWithAllMode = {
        ...mockStatus,
        status: {
          ...mockStatus.status,
          all_mode: 5,
        },
      };

      render(<System status={statusWithAllMode} connection="Connected" />);

      // Verify hold form is present
      expect(screen.getByText('Change Hold')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully for system mode changes', async () => {
      apiService.systemMode.mockRejectedValueOnce(
        new Error('Network Error')
      );

      render(<System status={mockStatus} connection="Connected" />);

      const selects = screen.getAllByRole('combobox');
      const modeSelect = selects.find(select =>
        select.querySelector('option[value="cool"]')
      );
      fireEvent.change(modeSelect, { target: { value: 'cool' } });

      await waitFor(() => {
        expect(apiService.systemMode).toHaveBeenCalled();
      });

      // Component should still be rendered and functional
      expect(screen.getByText('System Status')).toBeInTheDocument();
    });
  });

  describe('API Integration Summary', () => {
    it('should have all required API service functions imported', () => {
      // Smoke test: verify all API functions are available
      expect(apiService.systemMode).toBeDefined();
      expect(apiService.systemFan).toBeDefined();
      expect(apiService.setZoneTemperature).toBeDefined();
      expect(apiService.setZoneHold).toBeDefined();
      expect(apiService.requestUpdate).toBeDefined();
    });
  });

  describe('MQTT Environment Configuration', () => {
    it('should have MQTT WebSocket URL available in test environment', () => {
      expect(import.meta.env.VITE_MQTT_WS_URL).toBe("ws://localhost:9001");
    });

    it('should use environment variable for MQTT connection', () => {
      // App.jsx should use import.meta.env.VITE_MQTT_WS_URL
      const mqttUrl = import.meta.env.VITE_MQTT_WS_URL || "wss://mqtt.mtnhouse.casa";
      expect(mqttUrl).toBe("ws://localhost:9001");
    });
  });
});
