/**
 * @vitest-environment happy-dom
 */
import { describe, it, expect, beforeEach } from "vitest";

describe("Environment Configuration", () => {
  describe("API Configuration", () => {
    it("should load API_BASE_URL from environment", () => {
      expect(import.meta.env.VITE_API_BASE_URL).toBe("http://localhost:8000");
    });

    it("should load API_TIMEOUT_MS from environment", () => {
      expect(import.meta.env.VITE_API_TIMEOUT_MS).toBe("5000");
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
});
