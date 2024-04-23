import './App.scss';

import { useEffect, useRef, useState } from 'react';

import System from './System';
import { data } from './json_response';
import mqtt from 'mqtt';
import mqttp from 'precompiled-mqtt';

export default function App() {
  const [connectionStatus, setConnectionStatus] = useState("Not Connected");
  const [initialUpdate, setInitialUpdate] = useState(false);
  const [CZ2Status, setCZ2Status] = useState(false);
  const [hvacTime, setHvacTime] = useState("");
  const [display, setDisplay] = useState(false);

  useEffect(() => {
    // const client = mqttp.connect("wss://mqtt.mtnhouse.casa");
    const client = mqtt.connect("wss://mqtt.mtnhouse.casa");

    // if (connectionStatus !== "Connected") {
    //   console.log("Trying to connect")
    //   if (status === 'development') {
    //     if(!CZ2Status){
    //       console.log("Setting Default Data")
    //       setCZ2Status(data)
    //       setDisplay(true)      
    //     }
    //   }
    // }
    if (connectionStatus !== "Connected" && initialUpdate === false) {
      console.log("Initial Update")
      // axios.get('https://nodered.mtnhouse.casa/hvac/update')
      //   .then((response) => {
      //     console.log(response.data)
      //   }).catch(error => {
      //     console.log(error)
      // })
      setInitialUpdate(true)
    }
    client.on('connect', () => {
      console.log('Connected');
      client.subscribe('hvac/cz2');
      setConnectionStatus("Connected");
    });
    client.on('message', (topic, payload, packet) => {
      // setMessages(messages.concat(payload.toString()));
      if (topic === 'hvac/cz2') {
        // console.log(payload.toString())
        let json_payload = JSON.parse(payload.toString())
        if (json_payload['time'] !== hvacTime){
          setCZ2Status(json_payload);
          setHvacTime(json_payload['time'])    
          setDisplay(true)      
        }
      }
    });
    client.on('error', (err) => {
      console.error('Connection error: ', err);
      client.end();
    });
  }, []);


  return (
    <div>
      {display ? <System status={CZ2Status} connection={connectionStatus}></System> : "Loading..."}
    </div>
  )
}