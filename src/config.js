// Centralized runtime config with sensible fallbacks
// Priority: window.__MOUNTAINSTAT_CONFIG__ (from /config.js) -> Vite env -> defaults

const runtime = (typeof window !== 'undefined' && window.__MOUNTAINSTAT_CONFIG__) || {};

export const CONFIG = {
  apiBaseUrl:
    runtime.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_BASE_URL ||
    (typeof window !== 'undefined' && window.location?.origin)
    || 'http://localhost:8000',
  apiTimeoutMs:
    Number(runtime.VITE_API_TIMEOUT_MS || import.meta.env.VITE_API_TIMEOUT_MS || 5000),
  mqttWsUrl:
    runtime.VITE_MQTT_WS_URL ||
    import.meta.env.VITE_MQTT_WS_URL ||
    (typeof window !== 'undefined' && window.location?.protocol === 'https:'
      ? 'wss://mqtt.mtnhouse.casa'
      : 'ws://localhost:9001'),
};

export default CONFIG;
