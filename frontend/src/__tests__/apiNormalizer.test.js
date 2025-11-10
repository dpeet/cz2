/**
 * Unit Tests for API Normalizer
 *
 * Verifies that apiNormalizer correctly handles both structured
 * and flat payloads from REST API and MQTT sources.
 */

import { describe, it, expect } from "vitest";
import { normalizeStatus, shouldDisableControls } from "../apiNormalizer";

describe("apiNormalizer", () => {
  describe("normalizeStatus", () => {
    it("should handle structured response with status and meta", () => {
      const payload = {
        status: {
          system_mode: "Heat",
          fan_mode: "Auto",
          all_mode: 0,
          zones: [
            { temperature: 70, heat_setpoint: 68, cool_setpoint: 75 },
          ],
        },
        meta: {
          connected: true,
          stale: false,
          cache_age_seconds: 10,
        },
      };

      const result = normalizeStatus(payload);

      expect(result.status).toEqual(payload.status);
      expect(result.meta).toEqual(payload.meta);
      expect(result.controlsDisabledReason).toBeNull();
    });

    it("should handle flat payload (MQTT-style)", () => {
      const payload = {
        system_mode: "Cool",
        fan_mode: "Auto",
        all_mode: 1,
        time: 1676180543,
        zones: [
          { temperature: 72, heat_setpoint: 68, cool_setpoint: 75 },
        ],
      };

      const result = normalizeStatus(payload);

      expect(result.status.system_mode).toBe("Cool");
      expect(result.status.fan_mode).toBe("Auto");
      expect(result.status.zones).toEqual(payload.zones);
      expect(result.meta.connected).toBe(true);
      expect(result.meta.stale).toBe(false);
      expect(result.controlsDisabledReason).toBeNull();
    });

    it("should extract meta fields from flat payload if present", () => {
      const payload = {
        system_mode: "Auto",
        fan_mode: "On",
        all_mode: 0,
        zones: [],
        connected: false,
        stale: true,
        cache_age_seconds: 300,
      };

      const result = normalizeStatus(payload);

      expect(result.status.system_mode).toBe("Auto");
      expect(result.status.connected).toBeUndefined();
      expect(result.status.stale).toBeUndefined();
      expect(result.meta.connected).toBe(false);
      expect(result.meta.stale).toBe(true);
      expect(result.meta.cache_age_seconds).toBe(300);
      expect(result.controlsDisabledReason).toBe("HVAC system not connected");
    });

    it("should handle null/undefined payload", () => {
      const result = normalizeStatus(null);

      expect(result.status).toBeNull();
      expect(result.meta.connected).toBe(false);
      expect(result.meta.stale).toBe(true);
      expect(result.controlsDisabledReason).toBe("No data available");
    });

    it("should handle unknown payload format", () => {
      const payload = { foo: "bar", baz: 123 };

      const result = normalizeStatus(payload);

      expect(result.status).toEqual(payload);
      expect(result.meta.connected).toBe(false);
      expect(result.meta.error).toBe("Unknown payload format");
      expect(result.controlsDisabledReason).toBe("Invalid data format");
    });

    it("should preserve numeric all_mode from flat payload", () => {
      const payload = {
        system_mode: "Heat",
        all_mode: 5,
        zones: [],
      };

      const result = normalizeStatus(payload);

      expect(result.status.all_mode).toBe(5);
      expect(typeof result.status.all_mode).toBe("number");
    });

    it("should preserve string damper_position in zones", () => {
      const payload = {
        system_mode: "Cool",
        zones: [
          { temperature: 70, damper_position: "75" },
        ],
      };

      const result = normalizeStatus(payload);

      expect(result.status.zones[0].damper_position).toBe("75");
      expect(typeof result.status.zones[0].damper_position).toBe("string");
    });

    it("should preserve time field from MQTT payload", () => {
      const payload = {
        system_mode: "Auto",
        time: 1676180543,
        zones: [],
      };

      const result = normalizeStatus(payload);

      expect(result.status.time).toBe(1676180543);
    });
  });

  describe("shouldDisableControls", () => {
    it("should return disabled=false when controls are enabled", () => {
      const normalized = {
        status: { system_mode: "Heat" },
        meta: { connected: true, stale: false },
        controlsDisabledReason: null,
      };

      const result = shouldDisableControls(normalized);

      expect(result.disabled).toBe(false);
      expect(result.reason).toBeNull();
    });

    it("should return disabled=true when data is stale", () => {
      const normalized = {
        status: { system_mode: "Heat" },
        meta: { connected: true, stale: true, cache_age_seconds: 300 },
        controlsDisabledReason: "Data is stale (300s old)",
      };

      const result = shouldDisableControls(normalized);

      expect(result.disabled).toBe(true);
      expect(result.reason).toBe("Data is stale (300s old)");
    });

    it("should return disabled=true when not connected", () => {
      const normalized = {
        status: { system_mode: "Heat" },
        meta: { connected: false, stale: false },
        controlsDisabledReason: "HVAC system not connected",
      };

      const result = shouldDisableControls(normalized);

      expect(result.disabled).toBe(true);
      expect(result.reason).toBe("HVAC system not connected");
    });

    it("should return disabled=true when backend error present", () => {
      const normalized = {
        status: { system_mode: "Heat" },
        meta: { connected: true, stale: false, error: "Timeout" },
        controlsDisabledReason: "Backend error: Timeout",
      };

      const result = shouldDisableControls(normalized);

      expect(result.disabled).toBe(true);
      expect(result.reason).toBe("Backend error: Timeout");
    });

    it("should handle missing normalized object", () => {
      const result = shouldDisableControls(null);

      expect(result.disabled).toBe(true);
      expect(result.reason).toBe("No data available");
    });

    it("should handle missing meta", () => {
      const normalized = { status: { system_mode: "Heat" } };

      const result = shouldDisableControls(normalized);

      expect(result.disabled).toBe(true);
      expect(result.reason).toBe("No data available");
    });
  });

  describe("Integration scenarios", () => {
    it("should normalize MQTT message then check controls", () => {
      const mqttPayload = {
        system_mode: "Heat",
        fan_mode: "Auto",
        all_mode: 0,
        zones: [{ temperature: 70 }],
      };

      const normalized = normalizeStatus(mqttPayload);
      const controlCheck = shouldDisableControls(normalized);

      expect(normalized.status.system_mode).toBe("Heat");
      expect(controlCheck.disabled).toBe(false);
    });

    it("should normalize stale API response then disable controls", () => {
      const apiPayload = {
        status: { system_mode: "Cool", zones: [] },
        meta: { connected: true, stale: true, cache_age_seconds: 600 },
      };

      const normalized = normalizeStatus(apiPayload);
      const controlCheck = shouldDisableControls(normalized);

      expect(normalized.status.system_mode).toBe("Cool");
      expect(controlCheck.disabled).toBe(true);
      expect(controlCheck.reason).toContain("stale");
    });

    it("should normalize offline backend response", () => {
      const apiPayload = {
        status: { system_mode: "Unknown", zones: [] },
        meta: { connected: false, stale: true },
      };

      const normalized = normalizeStatus(apiPayload);
      const controlCheck = shouldDisableControls(normalized);

      expect(controlCheck.disabled).toBe(true);
      expect(controlCheck.reason).toBe("HVAC system not connected");
    });
  });
});
