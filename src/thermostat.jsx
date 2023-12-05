import classNames from 'classnames';

function Thermostat(props) {

    // TODO change the "disable" state to not disable the temp color
    let thermostatClasses = classNames({
        'thermostat': true,
        allmode: props.allMode,
    });

    return (
        <div className={thermostatClasses}>
            <div className='Zone'>Zone {props.zone}</div>
            <div className='humidity'>
                {props.humidity && <h3 className='humidity'>Humidity: {props.humidity}%</h3>}
            </div>
            
            
            <div className='currTemp'>
                <h1>{props.displayTemp}°F</h1>
            </div>
            <div className='setTemps'>
                <h2 className='heatSetPoint'>{props.heatSetPoint}</h2>
                {props.hold && <h2 className='hold'>{"Hold"}</h2>}
                <h2 className='coolSetPoint'>{props.coolSetPoint}</h2>
            </div>
            {/* <input type="range" min="60" max="80" value={temperatureDisplay} onChange={handleTemperatureDisplayChange} /> */}
        </div>
    );
}

export default Thermostat;