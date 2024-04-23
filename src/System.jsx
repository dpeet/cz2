import './App.scss';

import axios, { all } from 'axios';
import { useEffect, useState } from 'react';

import CircleLoader from "react-spinners/CircleLoader";
import Thermostat from './thermostat';

export default function System(props) {
    const [CZ2Status, setCZ2Status] = useState(props.status);
    // const [cz2messages, setCZ2Messages] = useState([]);
    const [zone1temp, setZone1Temp] = useState(null);
    const [zone1Humidity, setZone1Humidity] = useState(null);
    const [zone1CoolSetPoint, setZone1CoolSetPoint] = useState(null);
    const [zone1HeatSetPoint, setZone1HeatSetPoint] = useState(null);
    const [zone1Hold, setZone1Hold] = useState(null);
    const [zone2temp, setZone2Temp] = useState(null);
    const [zone2CoolSetPoint, setZone2CoolSetPoint] = useState(null);
    const [zone2HeatSetPoint, setZone2HeatSetPoint] = useState(null);
    const [zone2Hold, setZone2Hold] = useState(null);
    const [zone3temp, setZone3Temp] = useState(null);
    const [zone3CoolSetPoint, setZone3CoolSetPoint] = useState(null);
    const [zone3HeatSetPoint, setZone3HeatSetPoint] = useState(null);
    const [zone3Hold, setZone3Hold] = useState(null);
    const [allMode, setAllMode] = useState(null);
    const [allModeButtonLabel, setAllModeButtonLabel] = useState('');
    const [zoneSelection, setZoneSelection] = useState('');
    const [modeSelection, setModeSelection] = useState('');
    const [targetTemperatureSelection, setTargetTemperatureSelection] = useState('');
    const [isTempChangeLoading, setIsTempChangeLoading] = useState(false);
    const [isSystemModeChangeLoading, setIsSystemModeChangeLoading] = useState(false);
    const [isFanModeChangeLoading, setIsFanModeChangeLoading] = useState(false);
    const [isAllModeChangeLoading, setIsAllModeChangeLoading] = useState(false);
    const [isHoldStatusChangeLoading, setIsHoldStatusChangeLoading] = useState(false);
    const [allHoldStatusButtonLabel, setAllHoldStatusButtonLabel] = useState('Set Hold On');
    const [systemMode, setSystemMode] = useState('Unknown');
    const [systemModeSelection, setSystemModeSelection] = useState('');
    const [systemFanMode, setSystemFanMode] = useState('Unknown');
    const [systemFanModeButtonLabel, setSystemFanModeButtonLabel] = useState('');
    const [lastUpdated, setLastUpdated] = useState('Never');

    useEffect(() => { setCZ2Status(props.status) }, [props.status]);

    useEffect(() => {
        console.log(CZ2Status)
        if(typeof(props.status) !== 'undefined') {
            setZone1Temp(CZ2Status['zones'][0]['temperature']);
            setZone1Humidity(CZ2Status['zone1_humidity']);
            setZone2Temp(CZ2Status['zones'][1]['temperature']);
            setZone3Temp(CZ2Status['zones'][2]['temperature']);
            setZone1CoolSetPoint(CZ2Status['zones'][0]['cool_setpoint']);
            setZone2CoolSetPoint(CZ2Status['zones'][1]['cool_setpoint']);
            setZone3CoolSetPoint(CZ2Status['zones'][2]['cool_setpoint']);
            setZone1HeatSetPoint(CZ2Status['zones'][0]['heat_setpoint']);
            setZone2HeatSetPoint(CZ2Status['zones'][1]['heat_setpoint']);
            setZone3HeatSetPoint(CZ2Status['zones'][2]['heat_setpoint']);
            setZone1Hold(CZ2Status['zones'][0]['hold']);
            setZone2Hold(CZ2Status['zones'][1]['hold']);
            setZone3Hold(CZ2Status['zones'][2]['hold']);
            if (CZ2Status['zones'][0]['hold'] >= 1 || CZ2Status['zones'][1]['hold'] >= 1 || CZ2Status['zones'][2]['hold'] >= 1) setAllHoldStatusButtonLabel("Set Hold Off")
            else if (CZ2Status['zones'][0]['hold'] == 0 && CZ2Status['zones'][1]['hold'] == 0 && CZ2Status['zones'][2]['hold'] == 0) setAllHoldStatusButtonLabel("Set Hold On")
            setAllMode(CZ2Status['all_mode']);
            CZ2Status['all_mode'] === 1 ? setZoneSelection("all") : null;
            if (CZ2Status['all_mode'] >= 1 && CZ2Status['all_mode'] <= 8) setAllModeButtonLabel("Set All Mode Off")
            else if (CZ2Status['all_mode'] === 0) setAllModeButtonLabel("Set All Mode On")
            setSystemMode(CZ2Status['system_mode']);
            setSystemFanMode(CZ2Status['fan_mode']);
            if (CZ2Status['fan_mode'] === "Auto") setSystemFanModeButtonLabel("Set Always On")
            else if (CZ2Status['fan_mode'] === "Always On") setSystemFanModeButtonLabel("Set Auto")
            setLastUpdated(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
        }
    }, [props.status]);

    const handleTempZoneChange = (event) => {
        setZoneSelection(event.target.value);
    };

    const handleTempModeChange = (event) => {
        setModeSelection(event.target.value);
    };

    const handleTargetTemperatureChange = (event) => {
        setTargetTemperatureSelection(parseInt(event.target.value));
    };

    const handleSystemModeChange = (event) => {
        setSystemModeSelection(event.target.value);
        setIsSystemModeChangeLoading(true);
        axios.get(`https://nodered.mtnhouse.casa/hvac/system/mode?mode=${event.target.value}`)
            .then((response) => {
                console.log(response.data)
                setIsSystemModeChangeLoading(false)
            }).catch(error => {
                console.log(error)
                setIsSystemModeChangeLoading(false)
            })
        setSystemModeSelection("");
    };

    const handleFanModeChange = (event) => {
        // TODO this should really be a better toggle, but it's manually setting everything now
        // ie buttonlabel should update automatically, not be set everywhere
        setIsFanModeChangeLoading(true);
        let fan_mode_desired = null
        if (systemFanMode === "Auto") fan_mode_desired = "always_on"
        if (systemFanMode === "Always On") fan_mode_desired = "auto"
        axios.get(`https://nodered.mtnhouse.casa/hvac/system/fan?fan=${fan_mode_desired}`)
            .then((response) => {
                console.log(response.data)
                if (systemFanMode === "Auto") {
                    setSystemFanMode("Always On");
                    setSystemFanModeButtonLabel("Set Auto")
                }
                else if (systemFanMode === "Always On") {
                    setSystemFanMode("Auto");
                    setSystemFanModeButtonLabel("Set Always On")

                }
                else console.log("systemFanMode broken")
                setIsFanModeChangeLoading(false)
            }).catch(error => {
                console.log(error)
            })
    }

    const handleAllModeChange = (event) => {
        // TODO this should really be a better toggle, but it's manually setting everything now
        // ie buttonlabel should update automatically, not be set everywhere
        setIsAllModeChangeLoading(true);
        let all_mode_desired = null
        if ( allMode >= 1 && allMode <= 8) all_mode_desired = "off"
        if (allMode === 0) all_mode_desired = "on"
        axios.get(`https://nodered.mtnhouse.casa/hvac/system/allmode?mode=${all_mode_desired}`)
            .then((response) => {
                console.log(response.data)
                if (allMode >= 1 && allMode <= 8) {
                    setAllMode(allMode);
                    setAllModeButtonLabel("Set Off")
                }
                else if (allMode === 0) {
                    setAllMode(0);
                    setAllModeButtonLabel("Set On")

                }
                else console.log("allMode broken")
                setIsAllModeChangeLoading(false)
            }).catch(error => {
                console.log(error)
                setIsAllModeChangeLoading(false)
            })
    }

    const handleHoldStatusChange = (event) => {
        if (allMode){
            setIsHoldStatusChangeLoading(true);
            let hold_status_desired = null
            if (zone1Hold >= 1 || zone2Hold >= 1 || zone3Hold >= 1) {
                hold_status_desired = "off"
                axios.get(`https://nodered.mtnhouse.casa/hvac/sethold?zone=${zone1Hold}&setHold=${hold_status_desired}`)
                .then((response) => {
                    console.log(response.data)
                    setZone1Hold(1);
                    setZone2Hold(1);
                    setZone3Hold(1);
                    setAllHoldStatusButtonLabel("Set Hold On")
                    setIsHoldStatusChangeLoading(false)
                }).catch(error => {
                    console.log("holdStatus broken")
                    console.log(error)
                    setIsHoldStatusChangeLoading(false)
                })
            }
            else if (zone1Hold == 0 && zone2Hold == 0 && zone3Hold == 0) {
                hold_status_desired = "on"
                axios.get(`https://nodered.mtnhouse.casa/hvac/sethold?zone=all&setHold=${hold_status_desired}`)
                .then((response) => {
                    console.log(response.data)
                    setZone1Hold(allMode);
                    setZone2Hold(allMode);
                    setZone3Hold(allMode);
                    setAllHoldStatusButtonLabel("Set Hold Off")
                    setIsHoldStatusChangeLoading(false)
                }).catch(error => {
                    console.log("holdStatus broken")
                    console.log(error)
                    setIsHoldStatusChangeLoading(false)
                })
            }
            else console.log("holdStatus numbers broken")
            
        }
        
        

    }

    const handleTempChangeSubmit = (event) => {
        event.preventDefault();
        setIsTempChangeLoading(true);

        axios.get(`https://nodered.mtnhouse.casa/hvac/settemp?mode=${modeSelection}&temp=${targetTemperatureSelection}&zone=${zoneSelection}`)
            .then((response) => {
                console.log(response.data)
                setIsTempChangeLoading(false)
            }).catch(error => {
                setError(error);
                console.log(error)
                setIsTempChangeLoading(false)
            })
    };

    const addHoverBorder = (event) => {
        event.target.classList.add("hover-border");
        console.log(event)
    }

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
                        hold={zone1Hold}
                    ></Thermostat>
                </div>
                <div className='secondary'>
                    <Thermostat
                        zone={2}
                        displayTemp={zone2temp}
                        coolSetPoint={zone2CoolSetPoint}
                        heatSetPoint={zone2HeatSetPoint}
                        allMode={allMode}
                        hold={zone2Hold}
                    ></Thermostat>
                    <Thermostat
                        zone={3}
                        displayTemp={zone3temp}
                        coolSetPoint={zone3CoolSetPoint}
                        heatSetPoint={zone3HeatSetPoint}
                        allMode={allMode}
                        hold={zone3Hold}
                    ></Thermostat>
                </div>

            </div>
            <div className='system_status'>
                <div className='title'>
                    <h1>System Status</h1>
                    <p>{`Connection Status: ${props.connection}`}</p>
                    {/* <p>Number of Updates: {cz2messages.length}</p> */}
                    <p>Last Updated: {lastUpdated}</p>
                </div>
                <div className='system_statuses'>
                    <div className='system_status_item'>
                        <div className='system_status_item_label'>
                            <p>Mode</p>
                            <h2>{systemMode}</h2>
                        </div>
                        <div className="form-group">
                            {systemMode === "Unknown" ?
                                <select className="system_disabled" disabled value={systemModeSelection} onChange={handleSystemModeChange} required>
                                    <option value="">Unknown</option>
                                </select>
                                :
                                <select className='hoverable' value={systemModeSelection} onChange={handleSystemModeChange} required>
                                    <option value=""> Select Mode</option>
                                    <option value="heat">Heat</option>
                                    <option value="cool">Cool</option>
                                    <option value="auto">Auto</option>
                                    <option value="off">Off</option>
                                </select>}
                        </div>
                        <CircleLoader loading={isSystemModeChangeLoading} size={20} /> 

                        {/* TODO right now this only loads while the mode is changed, but doesn't wait for an update */}
                        
                    </div>
                    <div className='system_status_item'>
                        <div className='system_status_item_label'>
                            <p>Fan</p>
                            <h2>{systemFanMode}</h2>
                        </div>
                        <div className="form-group">
                            {systemFanMode === "Unknown" && <button className="system_disabled" type="submit" disabled>Unknown</button>}
                            {(systemFanMode !== "Unknown" && isFanModeChangeLoading ) &&  <button className="system_disabled" type="submit" disabled> <CircleLoader size={16} /> Loading...</button>}
                            {(systemFanMode !== "Unknown" && !isFanModeChangeLoading ) &&
                                <button className="system" type="submit" onClick={handleFanModeChange}>
                                    {systemFanModeButtonLabel}
                                </button>}
                        </div>
                        {/* TODO right now this only loads while the mode is changed, but doesn't wait for an update */}
                        {/* <CircleLoader loading={} size={20} /> */}
                    </div>
                    <div className='system_status_item'>
                        <div className='system_status_item_label'>
                            <p>All Mode</p>
                            {allMode >= 1 && allMode <= 8 && <h2>On</h2>}
                            {allMode == 0 && <h2>Off</h2>}
                            {allMode == null && <h2>Unknown</h2>}
                        </div>
                        <div className="form-group">
                            {allMode === null && <button className="system_disabled" type="submit" disabled>Unknown</button>}
                            {(allMode !== null && isAllModeChangeLoading) && <button className="system_disabled" type="submit" disabled> <CircleLoader size={16} /> Loading...</button>}
                            {(allMode !== null && !isAllModeChangeLoading) && 
                            <button className="system" type="submit" onClick={handleAllModeChange}>
                                {allModeButtonLabel}
                                </button> }                
                        </div>
                        
                        {/* TODO right now this only loads while the mode is changed, but doesn't wait for an update */}
                        {/* <CircleLoader loading={} size={20} /> */}
                    </div>
                    
                </div>
                <div className='hold_control'>
                    <h2 className='change_hold'>Change Hold</h2>
                    <form className='hold-form'>
                        {allMode ?
                        <div>
                            <div className="form-group">
                                {zone1Hold >= 1 || zone2Hold >= 1 || zone3Hold >= 1 ? <h2>On</h2> : <h2>Off</h2>}
                            </div>
                            <div className='form-group'>
                                {isHoldStatusChangeLoading && <button className="system_disabled" type="submit" disabled> <CircleLoader size={16} /> Loading...</button>}
                                {!isHoldStatusChangeLoading && <button className="system" type="submit" onClick={handleHoldStatusChange}>
                                    {allHoldStatusButtonLabel} </button>}
                            </div>
                        </div>
                        :
                        <div className="form-group">
                            <label>Zone</label>
                            <select value={zoneSelection} onChange={handleTempZoneChange} required>
                                <option value="">Select Zone</option>
                                <option value="all">All</option>
                                <option value="1">1</option>
                                <option value="2">2</option>
                                <option value="3">3</option>
                            </select>
                        </div>}
                    </form>
                </div>
                <div className='temp_control'>
                    <h2 className='change_temp'>Change Temperature</h2>
                    <form className="thermostat-form" onSubmit={handleTempChangeSubmit}>
                        {allMode ?
                            <div className="form-group">
                                <label>Zone</label>
                                <select value={zoneSelection} onChange={handleTempZoneChange} disabled>
                                    <option value="all">All Zones</option>
                                </select>
                            </div>
                            :
                            <div className="form-group">
                                <label>Zone</label>
                                <select className='hoverable' value={zoneSelection} onChange={handleTempZoneChange} required>
                                    <option value="">Select Zone</option>
                                    <option value="all">All</option>
                                    <option value="1">1</option>
                                    <option value="2">2</option>
                                    <option value="3">3</option>
                                </select>
                            </div>}
                        <div className="form-group">
                            <label>Mode</label>
                            <select className="hoverable" value={modeSelection} onChange={handleTempModeChange} required>
                                <option value="">Select mode</option>
                                <option value="heat">Heat</option>
                                <option value="cool">Cool</option>
                            </select>

                        </div>
                        <div className="form-group">
                            <label>Target Temperature:</label>
                            <input type="number" min="45" max="80" value={targetTemperatureSelection} onChange={handleTargetTemperatureChange} required />
                        </div>
                        <button className="temp" type="submit" disabled={isTempChangeLoading}>
                            {isTempChangeLoading ? "Loading..." : "Submit"}
                        </button>
                    </form>
                </div>

            </div>
        </div>
    )
}