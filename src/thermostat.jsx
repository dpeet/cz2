import React, { useState } from 'react';
import classNames from 'classnames';

function Thermostat(props) {

    const handleTemperatureDisplayChange = (event) => {
        // setTemperatureDisplay(parseInt(event.target.value));
    };

    const thermostatClasses = classNames({
        'thermostat': true,
        allmode: props.allMode,
    });

    return (
        <div className={thermostatClasses}>
            Zone {props.zone}
            <div className='humidity'>
                {props.humidity && <h3 className='humidity'>{props.humidity}%</h3>}
            </div>
            
            
            <div className='currTemp'>
                <h1>{props.displayTemp}°F</h1>
            </div>
            <div className='setTemps'>
                <h2 className='heatSetPoint'>{props.heatSetPoint}</h2>
                <h2 className='coolSetPoint'>{props.coolSetPoint}</h2>
            </div>
            {/* <input type="range" min="60" max="80" value={temperatureDisplay} onChange={handleTemperatureDisplayChange} /> */}
        </div>
    );
}

export default Thermostat;