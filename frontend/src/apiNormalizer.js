/**
 * API Response Normalizer for Mountain House Thermostat
 *
 * This module normalizes responses from both REST API and MQTT sources
 * into a consistent structure, handling metadata for control disabling
 * and error states.
 *
 * Per MOUNTAINSTAT_MIGRATION_PLAN.md: provides unified interface for
 * both /status?flat=1 (MQTT) and structured API responses.
 */

/**
 * Normalize status payload from either REST or MQTT source
 *
 * @param {Object} payload - Raw payload from API or MQTT
 * @returns {Object} Normalized object with { status, meta, controlsDisabledReason }
 */
const coerceStatusShape = (status) => {
  if (!status) return status;
  const cloned = { ...status };
  // Normalize all_mode to number if boolean
  if (typeof cloned.all_mode === "boolean") {
    cloned.all_mode = cloned.all_mode ? 1 : 0;
  }
  // Normalize zones array
  if (Array.isArray(cloned.zones)) {
    cloned.zones = cloned.zones.map((z) => {
      const nz = { ...z };
      // Coerce hold true/false to 1/0 for UI comparisons
      if (typeof nz.hold === "boolean") {
        nz.hold = nz.hold ? 1 : 0;
      }
      return nz;
    });
  }
  return cloned;
};

export const normalizeStatus = (payload) => {
  if (!payload) {
    return {
      status: null,
      meta: { connected: false, stale: true },
      controlsDisabledReason: "No data available",
    };
  }

  // Case 1: Structured response with separate status and meta
  // (e.g., { status: {...}, meta: {...} })
  if (payload.status && payload.meta !== undefined) {
    const { status, meta } = payload;
    const statusCoerced = coerceStatusShape(status);
    const controlsDisabledReason = determineDisabledReason(meta);

    return {
      status: statusCoerced,
      meta,
      controlsDisabledReason,
    };
  }

  // Case 2: Flat payload (MQTT or /status?flat=1)
  // All status fields are at the top level; no separate meta object
  // Check for known status fields to distinguish from error responses
  if (payload.system_mode !== undefined || payload.zones !== undefined) {
    // Extract meta fields if present (backend may include them in flat mode)
    const meta = {
      connected: payload.connected !== undefined ? payload.connected : true,
      stale: payload.stale !== undefined ? payload.stale : false,
      cache_age_seconds: payload.cache_age_seconds,
      last_update_time: payload.last_update_time,
      error: payload.error,
    };

    // Remove meta fields from status to avoid duplication
  const status = coerceStatusShape({ ...payload });
    delete status.connected;
    delete status.stale;
    delete status.cache_age_seconds;
    delete status.last_update_time;
    delete status.error;

    const controlsDisabledReason = determineDisabledReason(meta);

    return {
      status,
      meta,
      controlsDisabledReason,
    };
  }

  // Case 3: Unknown/error payload - return as-is with error metadata
  return {
    status: payload,
    meta: { connected: false, stale: true, error: "Unknown payload format" },
    controlsDisabledReason: "Invalid data format",
  };
};

/**
 * Determine reason for disabling controls based on metadata
 *
 * @param {Object} meta - Metadata object
 * @returns {string|null} Reason string if controls should be disabled, null otherwise
 */
const determineDisabledReason = (meta) => {
  if (!meta) {
    return "No metadata available";
  }

  // Priority order: error > not connected > stale cache
  if (meta.error) {
    return `Backend error: ${meta.error}`;
  }

  if (meta.connected === false) {
    return "HVAC system not connected";
  }

  if (meta.stale === true) {
    const ageHint = meta.cache_age_seconds
      ? ` (${Math.floor(meta.cache_age_seconds)}s old)`
      : "";
    return `Data is stale${ageHint}`;
  }

  return null; // Controls enabled
};

/**
 * Determine if controls should be disabled
 *
 * @param {Object} normalized - Normalized status object from normalizeStatus()
 * @returns {Object} { disabled: boolean, reason: string|null }
 */
export const shouldDisableControls = (normalized) => {
  if (!normalized || !normalized.meta) {
    return { disabled: true, reason: "No data available" };
  }

  const reason = normalized.controlsDisabledReason;
  return {
    disabled: reason !== null,
    reason,
  };
};

export default {
  normalizeStatus,
  shouldDisableControls,
};
