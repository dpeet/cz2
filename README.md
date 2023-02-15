# Mountainstat

React App to act as a virtaul thermostat for the Mountain House.  Connects to a local MQTT broker and reads/writes thermostat data from the Carrier CV2 HVAC system.  

## To Install
`yarn`

## To Develop
`yarn run dev --host`
I connect with the tailscale IP, for some reason localhost ssh doesn't hot reload correctly

## To Build for HA / Caddy
`yarn run build`
