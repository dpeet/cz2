import "./App.scss";

import { useEffect, useState } from "react";

import CircleLoader from "react-spinners/CircleLoader";
import Thermostat from "./thermostat";
import {
  systemMode as setSystemModeApi,
  systemFan as setSystemFanApi,
  setZoneTemperature,
  setZoneHold,
  requestUpdate as requestUpdateApi
} from "./apiService";
import { normalizeStatus } from "./apiNormalizer";

const isTestEnv = import.meta.env.MODE === "test";

// Gate noisy console output during automated tests while keeping visibility in local dev
const logInfo = (...args) => {
    if (!isTestEnv) {
        console.log(...args);
    }
};

const logError = (...args) => {
    if (!isTestEnv) {
        console.error(...args);
    }
};

export default function System(props) {
    const [CZ2Status, setCZ2Status] = useState(props.status);
    const [error, setError] = useState(null);
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
    const [allModeButtonLabel, setAllModeButtonLabel] = useState("");
    const [zoneSelection, setZoneSelection] = useState("");
    const [modeSelection, setModeSelection] = useState("");
    const [targetTemperatureSelection, setTargetTemperatureSelection] = useState("");
    const [isTempChangeLoading, setIsTempChangeLoading] = useState(false);
    const [isSystemModeChangeLoading, setIsSystemModeChangeLoading] = useState(false);
    const [isFanModeChangeLoading, setIsFanModeChangeLoading] = useState(false);
    const [isAllModeChangeLoading, setIsAllModeChangeLoading] = useState(false);
    const [isHoldStatusChangeLoading, setIsHoldStatusChangeLoading] = useState(false);
    const [allHoldStatusButtonLabel, setAllHoldStatusButtonLabel] = useState("Set Hold On");
    const [systemMode, setSystemMode] = useState("Unknown");
    const [systemModeSelection, setSystemModeSelection] = useState("");
    const [systemFanMode, setSystemFanMode] = useState("Unknown");
    const [systemFanModeButtonLabel, setSystemFanModeButtonLabel] = useState("");
    const [lastUpdated, setLastUpdated] = useState("Never");

    useEffect(() => { setCZ2Status(props.status) }, [props.status]);

    useEffect(() => {
        if (typeof(props.status) !== "undefined" && props.status) {
            // Extract status from normalized object (props.status now contains normalized data)
            const statusData = props.status.status || props.status;

            if (statusData && statusData.zones && statusData.zones.length >= 3) {
                setZone1Temp(statusData.zones[0].temperature);
                setZone1Humidity(statusData.zone1_humidity);
                setZone2Temp(statusData.zones[1].temperature);
                setZone3Temp(statusData.zones[2].temperature);
                setZone1CoolSetPoint(statusData.zones[0].cool_setpoint);
                setZone2CoolSetPoint(statusData.zones[1].cool_setpoint);
                setZone3CoolSetPoint(statusData.zones[2].cool_setpoint);
                setZone1HeatSetPoint(statusData.zones[0].heat_setpoint);
                setZone2HeatSetPoint(statusData.zones[1].heat_setpoint);
                setZone3HeatSetPoint(statusData.zones[2].heat_setpoint);
                setZone1Hold(statusData.zones[0].hold);
                setZone2Hold(statusData.zones[1].hold);
                setZone3Hold(statusData.zones[2].hold);

                if (statusData.zones[0].hold >= 1 ||
                    statusData.zones[1].hold >= 1 ||
                    statusData.zones[2].hold >= 1) {
                    setAllHoldStatusButtonLabel("Set Hold Off");
                } else if (statusData.zones[0].hold === 0 &&
                           statusData.zones[1].hold === 0 &&
                           statusData.zones[2].hold === 0) {
                    setAllHoldStatusButtonLabel("Set Hold On");
                }

                setAllMode(statusData.all_mode);
                if (statusData.all_mode === 1) setZoneSelection("all");

                if (statusData.all_mode >= 1 && statusData.all_mode <= 8) {
                    setAllModeButtonLabel("Set All Mode Off");
                } else if (statusData.all_mode === 0) {
                    setAllModeButtonLabel("Set All Mode On");
                }

                setSystemMode(statusData.system_mode);
                setSystemFanMode(statusData.fan_mode);

                if (statusData.fan_mode === "Auto") {
                    setSystemFanModeButtonLabel("Set Always On");
                } else if (statusData.fan_mode === "Always On") {
                    setSystemFanModeButtonLabel("Set Auto");
                }

                setLastUpdated(new Date().toLocaleTimeString([],
                  { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
            }
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
        const newMode = event.target.value;
        setSystemModeSelection(newMode);
        setIsSystemModeChangeLoading(true);
        setError(null);

        // Use new POST API service (see apiService.js)
        setSystemModeApi(newMode)
            .then((response) => {
                const normalized = normalizeStatus(response);
                logInfo(normalized);
                setIsSystemModeChangeLoading(false);
            }).catch(error => {
                logError(error);
                setError(`Failed to set system mode: ${error.message}`);
                // TODO (clarify): Replace logError with user-facing toast/banner
                setIsSystemModeChangeLoading(false);
            });
        setSystemModeSelection("");
    };

    const handleFanModeChange = (event) => {
        // TODO this should really be a better toggle, but it's manually setting everything now
        // ie buttonlabel should update automatically, not be set everywhere
        setIsFanModeChangeLoading(true);
        setError(null);

        // Map frontend labels to backend API values (functional update)
        setSystemFanMode(prevMode => {
            const fanModeDesired = prevMode === "Auto" ? "On" : "Auto";

            // Use new POST API service (see apiService.js)
            setSystemFanApi(fanModeDesired)
                .then((response) => {
                    const normalized = normalizeStatus(response);
                    logInfo(normalized);

                    if (prevMode === "Auto") {
                        setSystemFanModeButtonLabel("Set Auto");
                    } else if (prevMode === "Always On") {
                        setSystemFanModeButtonLabel("Set Always On");
                    }
                    setIsFanModeChangeLoading(false);
                }).catch(error => {
                    logError(error);
                    setError(`Failed to set fan mode: ${error.message}`);
                    // TODO (clarify): Replace logError with user-facing toast/banner
                    setIsFanModeChangeLoading(false);
                });

            return prevMode === "Auto" ? "Always On" : "Auto";
        });
    }

    const handleAllModeChange = (event) => {
        // TODO this should really be a better toggle, but it's manually setting everything now
        // ie buttonlabel should update automatically, not be set everywhere
        setIsAllModeChangeLoading(true);
        setError(null);

        // Determine desired all-mode setting (functional update)
        setAllMode(prevAllMode => {
            const allModeDesired = (prevAllMode >= 1 && prevAllMode <= 8) ? false : true;
            const currentSystemMode = systemMode || "Auto";

            // Use new POST API service: systemMode with all=true/false (see apiService.js)
            setSystemModeApi(currentSystemMode, { all: allModeDesired })
                .then((response) => {
                    const normalized = normalizeStatus(response);
                    logInfo(normalized);

                    if (prevAllMode >= 1 && prevAllMode <= 8) {
                        setAllModeButtonLabel("Set On");
                    } else if (prevAllMode === 0) {
                        setAllModeButtonLabel("Set Off");
                    }
                    setIsAllModeChangeLoading(false);
                }).catch(error => {
                    logError(error);
                    setError(`Failed to set all mode: ${error.message}`);
                    // TODO (clarify): Replace logError with user-facing toast/banner
                    setIsAllModeChangeLoading(false);
                });

            return prevAllMode;
        });
    }

    const handleHoldStatusChange = (event) => {
        if (allMode){
            setIsHoldStatusChangeLoading(true);
            setError(null);

            // Determine desired hold state (true = enable, false = disable)
            const holdStatusDesired = (zone1Hold >= 1 || zone2Hold >= 1 || zone3Hold >= 1)
              ? false
              : true;

            // Extract actual status from normalized object
            const statusData = CZ2Status.status || CZ2Status;

            // Use new POST API service: setZoneHold("all", hold, cachedStatus)
            // (see apiService.js)
            setZoneHold("all", holdStatusDesired, statusData)
                .then((responses) => {
                    // Normalize each response
                    const normalized = responses.map(r => normalizeStatus(r));
                    logInfo(normalized);

                    if (holdStatusDesired) {
                        // Hold enabled
                        setZone1Hold(allMode);
                        setZone2Hold(allMode);
                        setZone3Hold(allMode);
                        setAllHoldStatusButtonLabel("Set Hold Off");
                    } else {
                        // Hold disabled
                        setZone1Hold(0);
                        setZone2Hold(0);
                        setZone3Hold(0);
                        setAllHoldStatusButtonLabel("Set Hold On");
                    }

                    setIsHoldStatusChangeLoading(false);
                }).catch(error => {
                    logError("Failed to set hold status:", error);
                    setError(`Failed to set hold status: ${error.message}`);
                    // TODO (clarify): Replace logError with user-facing toast/banner
                    setIsHoldStatusChangeLoading(false);
                });
        }
    }

    const handleTempChangeSubmit = (event) => {
        event.preventDefault();
        setIsTempChangeLoading(true);
        setError(null);

        // Validate temperature range (45-80°F)
        if (targetTemperatureSelection < 45 || targetTemperatureSelection > 80) {
            setError("Temperature out of range (45-80°F)");
            // TODO (clarify): Replace with user-facing error toast/banner
            setIsTempChangeLoading(false);
            return;
        }

        // Extract actual status from normalized object
        const statusData = CZ2Status.status || CZ2Status;

        // Handle "all" zones by issuing parallel requests for each zone
        if (zoneSelection === "all" && statusData && statusData.zones) {
            const promises = statusData.zones.map((_, index) => {
                const zoneId = index + 1;
                return setZoneTemperature(zoneId, {
                    mode: modeSelection,
                    temp: targetTemperatureSelection,
                    tempFlag: true,
                });
            });

            Promise.all(promises)
                .then((responses) => {
                    // Normalize each response
                    const normalized = responses.map(r => normalizeStatus(r));
                    logInfo(normalized);
                    setIsTempChangeLoading(false);
                })
                .catch(error => {
                    logError(error);
                    setError(`Failed to set temperature: ${error.message}`);
                    // TODO (clarify): Replace logError with user-facing toast/banner
                    setIsTempChangeLoading(false);
                });
        } else {
            // Single zone: Use new POST API service (see apiService.js)
            setZoneTemperature(parseInt(zoneSelection), {
                mode: modeSelection,
                temp: targetTemperatureSelection,
                tempFlag: true,
            })
                .then((response) => {
                    const normalized = normalizeStatus(response);
                    logInfo(normalized);
                    setIsTempChangeLoading(false);
                }).catch(error => {
                    logError(error);
                    setError(`Failed to set temperature: ${error.message}`);
                    // TODO (clarify): Replace logError with user-facing toast/banner
                    setIsTempChangeLoading(false);
                });
        }
    };

    const addHoverBorder = (event) => {
        event.target.classList.add("hover-border");
    }

    return (
        <div className="app">
            {/* TODO (clarify): Replace simple error banner with toast/notification library */}
            {error && (
                <div style={{
                    backgroundColor: "#f44336",
                    color: "white",
                    padding: "10px",
                    margin: "10px",
                    borderRadius: "4px",
                    textAlign: "center"
                }}>
                    {error}
                    <button
                        onClick={() => setError(null)}
                        style={{
                            marginLeft: "10px",
                            padding: "5px 10px",
                            cursor: "pointer"
                        }}
                    >
                        Dismiss
                    </button>
                </div>
            )}
            <div className="thermostats">
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
