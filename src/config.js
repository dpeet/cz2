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

export const resolveConfig = () => {
  const runtime = resolveRuntimeConfig();
  const env = resolveEnv();

  return {
    apiBaseUrl:
      runtime.VITE_API_BASE_URL ||
      env.VITE_API_BASE_URL ||
      resolveWindowOrigin() ||
      "http://localhost:8000",
    apiTimeoutMs: Number(
      runtime.VITE_API_TIMEOUT_MS ??
        env.VITE_API_TIMEOUT_MS ??
        5000,
    ),
    mqttWsUrl:
      runtime.VITE_MQTT_WS_URL ||
      env.VITE_MQTT_WS_URL ||
      resolveMqttDefault(),
  };
};

export const CONFIG = resolveConfig();

export default CONFIG;
