/**
 * API Service for Mountain House Thermostat
 * Provides methods for interacting with the Python cz2 backend API
 */

import axios from "axios";
import { resolveConfig } from "./config";

// Get base URL from environment or fallback to window.location.origin
const getBaseUrl = () => resolveConfig().apiBaseUrl;

// Get API timeout from environment (configured via .env files)
const getTimeout = () => resolveConfig().apiTimeoutMs;

// Lazy-initialized axios instance to support testing
let apiClient = null;

// Get or create the axios client instance
const getApiClient = () => {
  if (!apiClient) {
    apiClient = axios.create({
      baseURL: getBaseUrl(),
      timeout: getTimeout(),
      headers: {
        "Content-Type": "application/json",
      },
    });
  }
  return apiClient;
};

// Reset the apiClient (for testing purposes)
export const resetApiClient = () => {
  apiClient = null;
};


/**
 * Set system mode (Heat, Cool, Auto, EHeat, Off)
 * @param {string} mode - The system mode to set
 * @param {Object} options - Additional options
 * @param {boolean} options.all - Enable/disable all-call mode (omitted if undefined)
 * @returns {Promise} Response with status and meta
 */
export const systemMode = async (mode, options = {}) => {
  const payload = { mode };

  // Only include 'all' if explicitly provided (can be true or false)
  if (options.all !== undefined) {
    payload.all = options.all;
  }

  const client = getApiClient();
  const response = await client.post("/system/mode", payload);
  return response.data;
};

/**
 * Set system fan mode (Auto or On)
 * @param {string} fan - The fan mode to set ("Auto" or "On")
 * @returns {Promise} Response with status and meta
 */
export const systemFan = async (fan) => {
  const client = getApiClient();
  const response = await client.post("/system/fan", { fan });
  return response.data;
};

/**
 * Set zone temperature setpoints
 * @param {number} zoneId - The zone ID (1-indexed)
 * @param {Object} options - Temperature options
 * @param {string} options.mode - 'heat' or 'cool'
 * @param {number} options.temp - Temperature value
 * @param {boolean} options.tempFlag - Optional temporary hold flag
 * @param {boolean} options.hold - Optional permanent hold flag
 * @returns {Promise} Response with status and meta
 */
export const setZoneTemperature = async (zoneId, options = {}) => {
  const { mode, temp } = options;
  const payload = {};

  // Build payload based on mode - backend expects 'heat' or 'cool' key
  if (mode === "heat") {
    payload.heat = temp;
  } else if (mode === "cool") {
    payload.cool = temp;
  }

  // Include optional flags if provided
  if (options.tempFlag !== undefined) {
    payload.temp = options.tempFlag;
  }
  if (options.hold !== undefined) {
    payload.hold = options.hold;
  }

  const client = getApiClient();
  const response = await client.post(`/zones/${zoneId}/temperature`, payload);
  return response.data;
};

/**
 * Set zone hold status
 * @param {number|string} zoneId - The zone ID or 'all' for all zones
 * @param {boolean} hold - Whether to enable or disable hold
 * @param {Object} cachedStatus - Cached status for determining zone count (required for 'all')
 * @returns {Promise} Response with status and meta (or array of responses for 'all')
 */
export const setZoneHold = async (zoneId, hold, cachedStatus = null) => {
  const client = getApiClient();

  // Handle 'all' zones - iterate through cached status
  if (zoneId === "all") {
    if (!cachedStatus || !cachedStatus.zones) {
      throw new Error("cachedStatus with zones array required when zoneId is 'all'");
    }

    // Issue parallel requests for all zones (1-indexed)
    const promises = cachedStatus.zones.map((_, index) => {
      const zoneNumber = index + 1;
      return client.post(`/zones/${zoneNumber}/hold`, {
        hold,
        temp: true,
      });
    });

    const responses = await Promise.all(promises);
    return responses.map(r => r.data);
  }

  // Single zone - post to specific zone endpoint
  const response = await client.post(`/zones/${zoneId}/hold`, {
    hold,
    temp: true,
  });
  return response.data;
};

/**
 * Request HVAC status update
 * @returns {Promise} Response with status and meta
 */
export const requestUpdate = async () => {
  const client = getApiClient();
  const response = await client.post("/update", {});
  return response.data;
};

export default {
  systemMode,
  systemFan,
  setZoneTemperature,
  setZoneHold,
  requestUpdate,
};
