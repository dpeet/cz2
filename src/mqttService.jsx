import mqtt from "precompiled-mqtt";
const websocketUrl = "ws://100.73.101.33:9001";
const apiEndpoint = "";

function getClient() {
  const client = mqtt.connect(websocketUrl);
  client.stream.on("connect", () => {
    console.log(`Connection to ${websocketUrl} succeeded`);
  });
  client.stream.on("error", (err) => {
    console.log(`Connection to ${websocketUrl} failed`);
    client.end();
  });
  return client;
}
function subscribe(client, topic) {
  const callBack = (err, granted) => {
    if (err) {
      console.log("error", err);
    }
    else if(granted) {
      console.log("granted", granted);
    }
  };
  console.log("subscribed to " + topic)
  return client.subscribe(apiEndpoint + topic, callBack);
}
function onMessage(client, callBack) {
  client.on("message", (topic, message, packet) => {
    callBack(JSON.parse(new TextDecoder("utf-8").decode(message)));
  });
}
function unsubscribe(client, topic) {
  client.unsubscribe(apiEndpoint + topic);
}
function closeConnection(client) {
  client.end();
}
const mqttService = {
  getClient,
  subscribe,
  onMessage,
  unsubscribe,
  closeConnection,
};
export default mqttService;