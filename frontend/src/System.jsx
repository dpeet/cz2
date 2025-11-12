import "./App.scss";

import { useEffect, useState } from "react";

import CircleLoader from "react-spinners/CircleLoader";
import { toast } from "sonner";
import Thermostat from "./thermostat";
import {
  systemMode as setSystemModeApi,
  systemFan as setSystemFanApi,
  setZoneTemperature,
  setBatchZoneTemperature,
  setZoneHold,
  requestUpdate as requestUpdateApi
} from "./apiService";
import { normalizeStatus } from "./apiNormalizer";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "./components/ui/tooltip";
import { tooltipContent } from "./tooltipContent";

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

/**
 * Extract a user-friendly error message from various error types
 * @param {Error} error - The error object from axios or other sources
 * @returns {string} A descriptive error message
 */
const getErrorMessage = (error) => {
    // Backend error with detail message (HTTPException)
    if (error.response?.data?.detail) {
        return error.response.data.detail;
    }

    // Axios timeout error - make it more user-friendly
    if (error.code === 'ECONNABORTED') {
        return 'Request timed out - the operation took too long to complete';
    }

    // Network/connection errors
    if (error.code === 'ERR_NETWORK') {
        return 'Network error - cannot reach the API server';
    }

    // Fall back to the generic error message
    return error.message || 'An unknown error occurred';
};

export default function System(props) {
    const [CZ2Status, setCZ2Status] = useState(props.status);
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
    const [singleZoneHoldButtonLabel, setSingleZoneHoldButtonLabel] = useState("Set Hold On");
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
                    setAllModeButtonLabel("Set All Zones Off");
                } else if (statusData.all_mode === 0) {
                    setAllModeButtonLabel("Set All Zones On");
                }

                setSystemMode(statusData.system_mode);
                // Backend sends "On" but we display "Always On" for clarity
                setSystemFanMode(statusData.fan_mode === "On" ? "Always On" : statusData.fan_mode);

                if (statusData.fan_mode === "Auto") {
                    setSystemFanModeButtonLabel("Set Always On");
                } else if (statusData.fan_mode === "On") {
                    setSystemFanModeButtonLabel("Set Auto");
                }

                setLastUpdated(new Date().toLocaleTimeString([],
                  { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
            }
        }
    }, [props.status]);

    // Helper function to get hold status for currently selected zone
    const getSelectedZoneHold = () => {
        switch(zoneSelection) {
            case "1": return zone1Hold;
            case "2": return zone2Hold;
            case "3": return zone3Hold;
            default: return null;
        }
    };

    // Update single zone hold button label when zone selection or hold status changes
    useEffect(() => {
        if (!allMode && zoneSelection && zoneSelection !== "" && zoneSelection !== "all") {
            const zoneHold = getSelectedZoneHold();
            if (zoneHold >= 1) {
                setSingleZoneHoldButtonLabel("Set Hold Off");
            } else if (zoneHold === 0) {
                setSingleZoneHoldButtonLabel("Set Hold On");
            }
        }
    }, [zoneSelection, zone1Hold, zone2Hold, zone3Hold, allMode]);

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

        // Immediate feedback
        toast.info("Command sent to HVAC", {
            description: `Setting mode to ${newMode}`
        });

        // Use new POST API service (see apiService.js)
        setSystemModeApi(newMode)
            .then((response) => {
                const normalized = normalizeStatus(response);
                logInfo(normalized);
                toast.success("System mode updated", {
                    description: `Mode changed to ${newMode}`
                });
                setIsSystemModeChangeLoading(false);
            }).catch(error => {
                logError(error);
                toast.error("Failed to set system mode", {
                    description: getErrorMessage(error)
                });
                setIsSystemModeChangeLoading(false);
            });
        setSystemModeSelection("");
    };

    const handleFanModeChange = (event) => {
        // TODO this should really be a better toggle, but it's manually setting everything now
        // ie buttonlabel should update automatically, not be set everywhere
        setIsFanModeChangeLoading(true);

        // Map displayed mode back to backend values: "Always On" -> "On"
        const currentBackendMode = systemFanMode === "Always On" ? "On" : systemFanMode;
        const fanModeDesired = currentBackendMode === "Auto" ? "On" : "Auto";
        const fanModeLabel = fanModeDesired === "On" ? "Always On" : "Auto";

        toast.info("Command sent to HVAC", {
            description: `Setting fan to ${fanModeLabel}`
        });

        // Use new POST API service (see apiService.js)
        setSystemFanApi(fanModeDesired)
            .then((response) => {
                const normalized = normalizeStatus(response);
                logInfo(normalized);

                // Update displayed mode and button label
                const newDisplayMode = fanModeDesired === "On" ? "Always On" : "Auto";
                setSystemFanMode(newDisplayMode);
                
                if (fanModeDesired === "On") {
                    setSystemFanModeButtonLabel("Set Auto");
                } else {
                    setSystemFanModeButtonLabel("Set Always On");
                }
                
                toast.success("Fan mode updated", {
                    description: `Fan mode changed to ${fanModeLabel}`
                });
                setIsFanModeChangeLoading(false);
            }).catch(error => {
                logError(error);
                toast.error("Failed to set fan mode", {
                    description: getErrorMessage(error)
                });
                setIsFanModeChangeLoading(false);
            });
    }

    const handleAllModeChange = (event) => {
        // TODO this should really be a better toggle, but it's manually setting everything now
        // ie buttonlabel should update automatically, not be set everywhere
        setIsAllModeChangeLoading(true);

        // Determine desired all-zones-mode setting
        const allModeDesired = (allMode >= 1 && allMode <= 8) ? false : true;
        const currentSystemMode = systemMode || "Auto";

        toast.info("Command sent to HVAC", {
            description: `${allModeDesired ? "Enabling" : "Disabling"} all zones mode`
        });

        // Use new POST API service: systemMode with all=true/false (see apiService.js)
        setSystemModeApi(currentSystemMode, { all: allModeDesired })
            .then((response) => {
                const normalized = normalizeStatus(response);
                logInfo(normalized);

                // Update state and button label
                const newAllMode = allModeDesired ? 1 : 0;
                setAllMode(newAllMode);
                
                if (allModeDesired) {
                    setAllModeButtonLabel("Set All Zones Off");
                } else {
                    setAllModeButtonLabel("Set All Zones On");
                }
                
                toast.success("Zone mode updated", {
                    description: `All zones mode ${allModeDesired ? "enabled" : "disabled"}`
                });
                setIsAllModeChangeLoading(false);
            }).catch(error => {
                logError(error);
                toast.error("Failed to set zone mode", {
                    description: getErrorMessage(error)
                });
                setIsAllModeChangeLoading(false);
            });
    }

    const handleHoldStatusChange = (event) => {
        event.preventDefault();
        
        setIsHoldStatusChangeLoading(true);

        // Determine desired hold state (true = enable, false = disable)
        const holdStatusDesired = (zone1Hold >= 1 || zone2Hold >= 1 || zone3Hold >= 1)
          ? false
          : true;

        // Immediate feedback
        toast.info("Command sent to HVAC", {
            description: `${holdStatusDesired ? "Enabling" : "Disabling"} hold for all zones`
        });

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
                    setZone1Hold(allMode || 1);
                    setZone2Hold(allMode || 1);
                    setZone3Hold(allMode || 1);
                    setAllHoldStatusButtonLabel("Set Hold Off");
                } else {
                    // Hold disabled
                    setZone1Hold(0);
                    setZone2Hold(0);
                    setZone3Hold(0);
                    setAllHoldStatusButtonLabel("Set Hold On");
                }

                toast.success("Hold status updated", {
                    description: `Hold ${holdStatusDesired ? "enabled" : "disabled"} for all zones`
                });
                setIsHoldStatusChangeLoading(false);
            }).catch(error => {
                logError("Failed to set hold status:", error);
                toast.error("Failed to set hold status", {
                    description: getErrorMessage(error)
                });
                setIsHoldStatusChangeLoading(false);
            });
    }

    const handleSingleZoneHoldStatusChange = (event) => {
        event.preventDefault();

        // Validate zone selection
        if (!zoneSelection || zoneSelection === "" || zoneSelection === "all") {
            toast.error("Invalid zone selection", {
                description: "Please select a specific zone (1, 2, or 3)"
            });
            return;
        }

        setIsHoldStatusChangeLoading(true);

        // Determine desired hold state for selected zone
        const zoneHold = getSelectedZoneHold();
        const holdStatusDesired = (zoneHold >= 1) ? false : true;

        // Immediate feedback
        toast.info("Command sent to HVAC", {
            description: `${holdStatusDesired ? "Enabling" : "Disabling"} hold for zone ${zoneSelection}`
        });

        // Extract actual status from normalized object
        const statusData = CZ2Status.status || CZ2Status;

        // Use POST API service: setZoneHold(zoneId, hold, cachedStatus)
        setZoneHold(zoneSelection, holdStatusDesired, statusData)
            .then((response) => {
                const normalized = normalizeStatus(response);
                logInfo(normalized);

                // Update specific zone's hold state
                const newHoldValue = holdStatusDesired ? (allMode || 1) : 0;
                switch(zoneSelection) {
                    case "1":
                        setZone1Hold(newHoldValue);
                        break;
                    case "2":
                        setZone2Hold(newHoldValue);
                        break;
                    case "3":
                        setZone3Hold(newHoldValue);
                        break;
                }

                // Update button label
                setSingleZoneHoldButtonLabel(holdStatusDesired ? "Set Hold Off" : "Set Hold On");

                toast.success("Hold status updated", {
                    description: `Hold ${holdStatusDesired ? "enabled" : "disabled"} for zone ${zoneSelection}`
                });
                setIsHoldStatusChangeLoading(false);
            })
            .catch(error => {
                logError("Failed to set hold status:", error);
                toast.error("Failed to set hold status", {
                    description: getErrorMessage(error)
                });
                setIsHoldStatusChangeLoading(false);
            });
    }

    const handleTempChangeSubmit = (event) => {
        event.preventDefault();
        setIsTempChangeLoading(true);

        // Validate temperature range (45-85°F)
        if (targetTemperatureSelection < 45 || targetTemperatureSelection > 85) {
            toast.error("Temperature out of range", {
                description: "Please enter a temperature between 45°F and 85°F"
            });
            setIsTempChangeLoading(false);
            return;
        }

        // Extract actual status from normalized object
        const statusData = CZ2Status.status || CZ2Status;

        // Handle "all" zones by issuing a single batch request
        if (zoneSelection === "all" && statusData && statusData.zones) {
            // Immediate feedback
            toast.info("Command sent to HVAC", {
                description: `Setting all zones to ${targetTemperatureSelection}°F (${modeSelection})`
            });

            // Get zone IDs from actual zones array (1-indexed)
            const zoneIds = statusData.zones.map((_, index) => index + 1);

            setBatchZoneTemperature(zoneIds, {
                mode: modeSelection,
                temp: targetTemperatureSelection,
                tempFlag: true,
            })
                .then((response) => {
                    // Normalize the response
                    const normalized = normalizeStatus(response);
                    logInfo(normalized);
                    toast.success("Temperature updated", {
                        description: `All zones set to ${targetTemperatureSelection}°F (${modeSelection})`
                    });
                    setIsTempChangeLoading(false);
                })
                .catch(error => {
                    logError(error);
                    toast.error("Failed to set temperature", {
                        description: getErrorMessage(error)
                    });
                    setIsTempChangeLoading(false);
                });
        } else {
            // Immediate feedback
            toast.info("Command sent to HVAC", {
                description: `Setting zone ${zoneSelection} to ${targetTemperatureSelection}°F (${modeSelection})`
            });

            // Single zone: Use new POST API service (see apiService.js)
            setZoneTemperature(parseInt(zoneSelection), {
                mode: modeSelection,
                temp: targetTemperatureSelection,
                tempFlag: true,
            })
                .then((response) => {
                    const normalized = normalizeStatus(response);
                    logInfo(normalized);
                    toast.success("Temperature updated", {
                        description: `Zone ${zoneSelection} set to ${targetTemperatureSelection}°F (${modeSelection})`
                    });
                    setIsTempChangeLoading(false);
                }).catch(error => {
                    logError(error);
                    toast.error("Failed to set temperature", {
                        description: getErrorMessage(error)
                    });
                    setIsTempChangeLoading(false);
                });
        }
    };

    const addHoverBorder = (event) => {
        event.target.classList.add("hover-border");
    }

    return (
        <TooltipProvider delayDuration={200}>
        <div className="app">
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
                            <p>
                                Mode
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <span style={{ marginLeft: '6px', cursor: 'help', opacity: 0.7 }}>ⓘ</span>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <div>
                                            <strong>{tooltipContent.mode.title}</strong>
                                            <p style={{ whiteSpace: 'pre-line', marginTop: '4px' }}>
                                                {tooltipContent.mode.description}
                                            </p>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            </p>
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
                            <p>
                                Fan
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <span style={{ marginLeft: '6px', cursor: 'help', opacity: 0.7 }}>ⓘ</span>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <div>
                                            <strong>{tooltipContent.fan.title}</strong>
                                            <p style={{ whiteSpace: 'pre-line', marginTop: '4px' }}>
                                                {tooltipContent.fan.description}
                                            </p>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            </p>
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
                            <p>
                                All Zone Mode
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <span style={{ marginLeft: '6px', cursor: 'help', opacity: 0.7 }}>ⓘ</span>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <div>
                                            <strong>{tooltipContent.allMode.title}</strong>
                                            <p style={{ whiteSpace: 'pre-line', marginTop: '4px' }}>
                                                {tooltipContent.allMode.description}
                                            </p>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            </p>
                            {allMode >= 1 && allMode <= 8 && <h2>All Zones</h2>}
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
                    <h2 className='change_hold'>
                        Change Hold
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <span style={{ marginLeft: '6px', cursor: 'help', opacity: 0.7 }}>ⓘ</span>
                            </TooltipTrigger>
                            <TooltipContent>
                                <div>
                                    <strong>{tooltipContent.hold.title}</strong>
                                    <p style={{ whiteSpace: 'pre-line', marginTop: '4px' }}>
                                        {tooltipContent.hold.description}
                                    </p>
                                </div>
                            </TooltipContent>
                        </Tooltip>
                    </h2>
                    <form className='hold-form'>
                        <div className="form-group">
                            <label>Zone</label>
                            <select className='hoverable' value={zoneSelection} onChange={handleTempZoneChange} required>
                                <option value="">Select Zone</option>
                                <option value="all">All Zones</option>
                                <option value="1">1</option>
                                <option value="2">2</option>
                                <option value="3">3</option>
                            </select>
                        </div>
                        {/* Show hold status and controls when a zone is selected */}
                        {zoneSelection && zoneSelection !== "" && (
                            <>
                                <div className="form-group">
                                    <label>Status</label>
                                    {zoneSelection === "all" ? (
                                        <h2>{zone1Hold >= 1 || zone2Hold >= 1 || zone3Hold >= 1 ? "On" : "Off"}</h2>
                                    ) : (
                                        <h2>{getSelectedZoneHold() >= 1 ? "On" : "Off"}</h2>
                                    )}
                                </div>
                                <div className='form-group'>
                                    {isHoldStatusChangeLoading && (
                                        <button className="system_disabled" type="submit" disabled>
                                            <CircleLoader size={16} /> Loading...
                                        </button>
                                    )}
                                    {!isHoldStatusChangeLoading && zoneSelection === "all" && (
                                        <button className="system" type="submit" onClick={handleHoldStatusChange}>
                                            {allHoldStatusButtonLabel}
                                        </button>
                                    )}
                                    {!isHoldStatusChangeLoading && zoneSelection !== "all" && (
                                        <button className="system" type="submit" onClick={handleSingleZoneHoldStatusChange}>
                                            {singleZoneHoldButtonLabel}
                                        </button>
                                    )}
                                </div>
                            </>
                        )}
                    </form>
                </div>
                <div className='temp_control'>
                    <h2 className='change_temp'>
                        Change Temperature
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <span style={{ marginLeft: '6px', cursor: 'help', opacity: 0.7 }}>ⓘ</span>
                            </TooltipTrigger>
                            <TooltipContent>
                                <div>
                                    <strong>{tooltipContent.temperature.title}</strong>
                                    <p style={{ whiteSpace: 'pre-line', marginTop: '4px' }}>
                                        {tooltipContent.temperature.description}
                                    </p>
                                </div>
                            </TooltipContent>
                        </Tooltip>
                    </h2>
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
                            <label>Target Temp:</label>
                            <input type="number" min="45" max="85" value={targetTemperatureSelection} onChange={handleTargetTemperatureChange} required />
                        </div>
                        {isTempChangeLoading && <button className="temp_disabled" type="submit" disabled><CircleLoader size={16} /> Loading...</button>}
                        {!isTempChangeLoading && <button className="temp" type="submit">Submit</button>}
                    </form>
                </div>

            </div>
        </div>
        </TooltipProvider>
    )
}
