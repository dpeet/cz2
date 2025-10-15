/**
 * @vitest-environment happy-dom
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { resolveConfig } from "../config.js";

describe("Environment Configuration", () => {
  describe("API Configuration", () => {
    it("should load API_BASE_URL from environment", () => {
      expect(import.meta.env.VITE_API_BASE_URL).toBe("http://localhost:8000");
    });

    it("should load API_TIMEOUT_MS from environment", () => {
      expect(import.meta.env.VITE_API_TIMEOUT_MS).toBe(process.env.VITE_API_TIMEOUT_MS);
    });
  });

  describe("MQTT Configuration", () => {
    it("should load MQTT_WS_URL from environment", () => {
      expect(import.meta.env.VITE_MQTT_WS_URL).toBe("ws://localhost:9001");
    });
  });

  describe("Fallback Behavior", () => {
    it("should define all required environment variables", () => {
      // Verify all required env vars are defined in test environment
      expect(import.meta.env.VITE_API_BASE_URL).toBeDefined();
      expect(import.meta.env.VITE_API_TIMEOUT_MS).toBeDefined();
  expect(import.meta.env.VITE_MQTT_WS_URL).toBeDefined();
    });
  });

  describe("resolveConfig", () => {
    beforeEach(() => {
  delete window.__MOUNTAINSTAT_CONFIG__;
    });

    afterEach(() => {
  delete window.__MOUNTAINSTAT_CONFIG__;
    });

    it("should throw error when timeout is missing or invalid", () => {
      window.__MOUNTAINSTAT_CONFIG__ = {
        VITE_API_TIMEOUT_MS: "",
      };

      // Save original and set to empty (in Vitest, import.meta.env reads from process.env)
      const originalTimeout = process.env.VITE_API_TIMEOUT_MS;
      process.env.VITE_API_TIMEOUT_MS = "";

      expect(() => resolveConfig()).toThrow('VITE_API_TIMEOUT_MS is not configured');

      // Restore original env
      process.env.VITE_API_TIMEOUT_MS = originalTimeout;
    });

  });
});
