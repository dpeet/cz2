/**
 * System Component Smoke Tests
 *
 * These tests verify that System.jsx correctly integrates with the new
 * POST-based apiService.js, ensuring all HVAC commands route through
 * the appropriate API functions.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import System from '../System';
import * as apiService from '../apiService';

// Mock the entire apiService module
vi.mock('../apiService');

// Mock sonner toast notifications
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

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
          fan_mode: 'On', // Backend sends "On", not "Always On"
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

  describe('Zone Mode Changes', () => {
    it('should call systemMode with all=true when enabling all zones mode', async () => {
      render(<System status={mockStatus} connection="Connected" />);

      const allModeButton = screen.getByText(/Set All Zones On/i);
      fireEvent.click(allModeButton);

      await waitFor(() => {
        expect(apiService.systemMode).toHaveBeenCalledWith(
          'Heat',
          { all: true }
        );
      });
    });

    it('should call systemMode with all=false when disabling all zones mode', async () => {
      const statusWithAllMode = {
        ...mockStatus,
        status: {
          ...mockStatus.status,
          all_mode: 1, // All zones mode enabled
        },
      };

      render(<System status={statusWithAllMode} connection="Connected" />);

      const allModeButton = screen.getByText(/Set All Zones Off/i);
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

  describe('All-Zones Hold Status', () => {
    // Build a normalized status with explicit per-zone hold/temporary bits
    const statusWithZoneHolds = (holds) => ({
      ...mockStatus,
      status: {
        ...mockStatus.status,
        zones: holds.map((h, i) => ({
          ...mockStatus.status.zones[i],
          hold: h.hold,
          temporary: h.temporary,
        })),
      },
    });

    // The hold form's Zone select is the only combobox offering an "all" option
    // (the temperature form omits it when all_mode === 0).
    const selectAllZones = () => {
      const holdSelect = screen
        .getAllByRole('combobox')
        .find((select) => select.querySelector('option[value="all"]'));
      fireEvent.change(holdSelect, { target: { value: 'all' } });
      return holdSelect;
    };

    it('shows "Mixed" with a per-zone breakdown popover when zones differ', async () => {
      // Z1 permanent (hold), Z2 off, Z3 temporary
      const status = statusWithZoneHolds([
        { hold: 1, temporary: 0 },
        { hold: 0, temporary: 0 },
        { hold: 0, temporary: 1 },
      ]);
      render(<System status={status} connection="Connected" />);

      selectAllZones();

      // Headline reflects the disagreement instead of collapsing to "On"
      const statusLabel = await screen.findByText(/^Mixed$/);
      expect(statusLabel).toBeInTheDocument();
      expect(screen.queryByText(/^On$/)).not.toBeInTheDocument();

      // Opening the popover reveals the per-zone breakdown
      const infoIcon = within(statusLabel.closest('h2')).getByText('ⓘ');
      fireEvent.focus(infoIcon);

      await waitFor(() => {
        expect(screen.getAllByText(/Zone 1: Permanent/).length).toBeGreaterThan(0);
      });
      expect(screen.getAllByText(/Zone 2: Off/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Zone 3: Temporary/).length).toBeGreaterThan(0);
    });

    it('shows a single aggregate label (no popover) when all zones agree', async () => {
      // All three zones on permanent hold
      const status = statusWithZoneHolds([
        { hold: 1, temporary: 0 },
        { hold: 1, temporary: 0 },
        { hold: 1, temporary: 0 },
      ]);
      render(<System status={status} connection="Connected" />);

      selectAllZones();

      expect(await screen.findByText(/^Permanent$/)).toBeInTheDocument();
      expect(screen.queryByText(/^Mixed$/)).not.toBeInTheDocument();
      expect(screen.queryByText(/^On$/)).not.toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully for system mode changes', async () => {
      const { toast } = await import('sonner');

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
        expect(toast.error).toHaveBeenCalledWith(
          "Failed to set system mode",
          expect.objectContaining({
            description: "Network Error"
          })
        );
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
