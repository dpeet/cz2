// Centralized runtime config with sensible fallbacks
// Priority: window.__MOUNTAINSTAT_CONFIG__ (from /config.js) -> Vite env -> defaults

const resolveRuntimeConfig = () => (
  (typeof window !== "undefined" && window.__MOUNTAINSTAT_CONFIG__) || {}
);

const resolveEnv = () => (
  (typeof import.meta !== "undefined" && import.meta.env) || {}
);

const resolveWindowOrigin = () => {
  if (typeof window === "undefined") return undefined;
  return window.location?.origin;
};

const resolveMqttDefault = () => {
  if (typeof window === "undefined") return "ws://localhost:9001";
  return window.location?.protocol === "https:" ? "wss://mqtt.mtnhouse.casa" : "ws://localhost:9001";
};

const pickFirst = (...values) => {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }
  return undefined;
};

export const resolveConfig = () => {
  const runtime = resolveRuntimeConfig();
  const env = resolveEnv();

  const baseUrl = pickFirst(
    runtime.VITE_API_BASE_URL,
    env.VITE_API_BASE_URL,
    resolveWindowOrigin(),
    "http://localhost:8000",
  );

  const timeout = Number(
    pickFirst(
      runtime.VITE_API_TIMEOUT_MS,
      env.VITE_API_TIMEOUT_MS,
    ),
  );

  const mqttUrl = pickFirst(
    runtime.VITE_MQTT_WS_URL,
    env.VITE_MQTT_WS_URL,
    resolveMqttDefault(),
  );

  // Validate required configuration
  if (!timeout || !Number.isFinite(timeout) || timeout <= 0) {
    throw new Error(
      'VITE_API_TIMEOUT_MS is not configured or invalid. Check your .env files.'
    );
  }

  return {
    apiBaseUrl: baseUrl,
    apiTimeoutMs: timeout,
    mqttWsUrl: mqttUrl,
  };
};

export const CONFIG = resolveConfig();

export default CONFIG;
