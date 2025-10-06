import "./App.scss";

import { useEffect, useRef, useState } from "react";

import System from "./System";
import mqtt from "mqtt";
import CONFIG from "./config";
import { normalizeStatus } from "./apiNormalizer";

export default function App() {
  const [connectionStatus, setConnectionStatus] = useState("Not Connected");
  const [initialUpdate, setInitialUpdate] = useState(false);
  const [CZ2Status, setCZ2Status] = useState(false);
  const [hvacTime, setHvacTime] = useState("");
  const [display, setDisplay] = useState(false);
  const reconnectTimer = useRef(null);
  const clientRef = useRef(null);

  useEffect(() => {
    // Resolve MQTT WebSocket URL with safe fallbacks
    // Priority: build-time env -> HTTPS-aware default
    const mqttUrl = CONFIG.mqttWsUrl;
    const client = mqtt.connect(mqttUrl, {
      reconnectPeriod: 3000, // 3s automatic reconnect by mqtt.js
      connectTimeout: 5000,
    });
    clientRef.current = client;

    // Request initial HVAC update on first connection attempt
    if (!initialUpdate) {
      console.log("Initial Update");
      setInitialUpdate(true);
    }

    client.on("connect", () => {
      console.log("Connected");
      // Subscribe to all CZ2 topics (covers legacy and new forms)
      client.subscribe("hvac/cz2/#");
      setConnectionStatus("Connected");
    });

    client.on("message", (topic, payload, packet) => {
      if (topic === "hvac/cz2" || topic === "hvac/cz2/status") {
        try {
          const jsonPayload = JSON.parse(payload.toString());
          // Normalize MQTT payload per MOUNTAINSTAT_MIGRATION_PLAN.md
          const normalized = normalizeStatus(jsonPayload);

          // Support both flat and structured payloads
          const statusPart = jsonPayload?.status ?? jsonPayload;
          const metaPart = jsonPayload?.meta ?? {};

          // Determine a message timestamp to de-dup frames
          const messageTime =
            statusPart?.time ??
            statusPart?.system_time ??
            metaPart?.last_update_time ??
            metaPart?.last_update_ts ??
            hvacTime;

          // Always show UI on first valid message
          if (!display) setDisplay(true);
          if (messageTime !== hvacTime) {
            setCZ2Status(normalized);
            setHvacTime(messageTime);
          }
        } catch (e) {
          console.error("Failed to parse MQTT payload", e);
        }
      }
    });

    client.on("error", (err) => {
      console.error("Connection error: ", err);
      // mqtt.js will auto-reconnect; don't end() here
      setConnectionStatus("Error (reconnecting)");
    });

    client.on("close", () => {
      setConnectionStatus("Disconnected (reconnecting)");
    });

    // Cleanup: close MQTT connection when component unmounts
    return () => {
      try { client.end(true); } catch {}
      clientRef.current = null;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };
  }, []);

  return (
    <div>
      {display ? (
        <System status={CZ2Status} connection={connectionStatus}></System>
      ) : (
        "Loading..."
      )}
    </div>
  );
}
