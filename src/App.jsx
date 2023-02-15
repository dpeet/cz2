import React from 'react';
import { useEffect, useState } from 'react';
import mqtt from 'precompiled-mqtt';
import Thermostat from './thermostat';
import './App.scss';
import {data} from './json_response';
import { createNoSubstitutionTemplateLiteral } from 'typescript';

export default function App() {
  const [connectionStatus, setConnectionStatus] = useState(false);
  const [messages, setMessages] = useState([]);
  const [cz2messages, setCZ2Messages] = useState([]);
  const [zone1temp, setZone1Temp] = useState(null);
  const [zone1Humidity, setZone1Humidity] = useState(null);
  const [zone1CoolSetPoint, setZone1CoolSetPoint] = useState(null);
  const [zone1HeatSetPoint, setZone1HeatSetPoint] = useState(null);
  const [zone2temp, setZone2Temp] = useState(null);
  const [zone2CoolSetPoint, setZone2CoolSetPoint] = useState(null);
  const [zone2HeatSetPoint, setZone2HeatSetPoint] = useState(null);
  const [zone3temp, setZone3Temp] = useState(null);
  const [zone3CoolSetPoint, setZone3CoolSetPoint] = useState(null);
  const [zone3HeatSetPoint, setZone3HeatSetPoint] = useState(null);
  const [allMode, setAllMode] = useState(null);
  
  const status = import.meta.env.PROD ? 'production' : 'development';

  const client = mqtt.connect("ws://100.73.101.33:9001");

  const setData = (data) => {
    console.log(data)
    setZone1Temp(data['zones'][0]['temperature']);
    setZone1Humidity(data['zone1_humidity']);
    setZone2Temp(data['zones'][1]['temperature']);
    setZone3Temp(data['zones'][2]['temperature']);
    setZone1CoolSetPoint(data['zones'][0]['cool_setpoint']);
    setZone2CoolSetPoint(data['zones'][1]['cool_setpoint']);
    setZone3CoolSetPoint(data['zones'][2]['cool_setpoint']);
    setZone1HeatSetPoint(data['zones'][0]['heat_setpoint']);
    setZone2HeatSetPoint(data['zones'][1]['heat_setpoint']);
    setZone3HeatSetPoint(data['zones'][2]['heat_setpoint']);
    setAllMode(data['all_mode'] = 1 ? true: false);
  }

  useEffect(() => {
    if(!connectionStatus) {
      console.log(client.connected)
      console.log("Setting Default Data")
      if (status === 'development') {
        setData(data)
      }
    }
    client.on('connect', () => {
      console.log('Connected');
      client.subscribe('hvac/cz2');
      setConnectionStatus(true);
    });
    client.on('message', (topic, payload, packet) => {
      setMessages(messages.concat(payload.toString()));
      if (topic === 'hvac/cz2') {
        let json_payload = JSON.parse(payload.toString())
        setCZ2Messages(messages.concat(json_payload));
        setData(json_payload)
      }
    });
    client.on('error', (err) => {
      console.error('Connection error: ', err);
      client.end();
    });
  }, [client]);

  return (
    <div className='app'>
      <div className='thermostats'>
        <div className='main'>
          <Thermostat 
            zone={1} 
            displayTemp={zone1temp}
            humidity={zone1Humidity}
            coolSetPoint={zone1CoolSetPoint}
            heatSetPoint={zone1HeatSetPoint}
          ></Thermostat>
        </div>
        <div className='secondary'>
          <Thermostat 
            zone={2} 
            displayTemp={zone2temp}
            coolSetPoint={zone2CoolSetPoint}
            heatSetPoint={zone2HeatSetPoint}
            allMode={allMode}
          ></Thermostat>
          <Thermostat 
            zone={3} 
            displayTemp={zone3temp}
            coolSetPoint={zone3CoolSetPoint}
            heatSetPoint={zone3HeatSetPoint}
            allMode={allMode}
          ></Thermostat>
        </div>
        
      </div>
      <div className='diagnostics'>
        <p>{`Connection Status: ${connectionStatus}`}</p>
        <p>Total Messages = {messages.length}</p>

        <h1>Zone 1 Temp: {zone1temp}</h1>
        <h1>Zone 2 Temp: {zone2temp}</h1>
        <h1>Zone 3 Temp: {zone3temp}</h1>

        {/* display the last message of the messages array */}
        <p>Last Message:</p>
        <p>{messages[messages.length - 1]}</p>

        {/* {messages.map((message) => (
        <h2 key={JSON.parse(message)['time']}>{JSON.parse(message)['time']} {message}</h2>
      ))} */}
      </div>

    </div>
  )
}