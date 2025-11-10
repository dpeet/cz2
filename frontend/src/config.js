// Centralized runtime config with sensible fallbacks
// Priority: window.__MOUNTAINSTAT_CONFIG__ (from /config.js) -> Vite env -> defaults

const resolveRuntimeConfig = () => (
  (typeof window !== "undefined" && window.__MOUNTAINSTAT_CONFIG__) || {}
);

const resolveEnv = () => (
  (typeof import.meta !== "undefined" && import.meta.env) || {}
);

const resolveApiBaseUrl = () => {
  if (typeof window === "undefined") return undefined;
  // Derive API URL from current hostname, changing only the port to 8000
  // This allows both localhost:5173 -> localhost:8000 and tailscale IP -> tailscale IP:8000
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8000`;
};

const resolveMqttDefault = () => {
  if (typeof window === "undefined") return "ws://localhost:9001";
  const { protocol, hostname } = window.location;
  
  // Production HTTPS -> production WSS
  if (protocol === "https:") return "wss://mqtt.mtnhouse.casa";
  
  // Dev mode: derive MQTT URL from current hostname (works for both localhost and Tailscale)
  // Assumes MQTT WebSocket is on port 9001 at same hostname as frontend
  return `ws://${hostname}:9001`;
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
    resolveApiBaseUrl(),
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
