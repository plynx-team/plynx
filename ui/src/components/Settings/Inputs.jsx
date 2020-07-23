import React from 'react';

const Inputs = (props) => {
    function InputType(props) {
        if (props.type === 'list'){
            return (
                <select 
                className={'list-input-' + props.title}
                onChange={props.input_change}
                defaultValue={props.choice}
                >
                    {
                        props.values.map((value) => {
                            return(
                                <option 
                                    value={value}
                                    key={value}
                                >
                                    {value}
                                </option>
                            )
                        })
                    }
                </select>
            )
        } else if (props.type === 'boolean') {
            return (
                <input 
                type="checkbox"
                className={'boolean-input-' + props.title}
                defaultChecked={props.choice ? "checked" : ""}
                onChange={props.input_change}
                />
            )
        }
    }

    return (
        <div className='option-wrapper'>
          {
            Object.keys(props.options).map(function(key) {
              return (
                <div className='option-cell' key={key}>
                    <div className='cell-title'>{key}</div>
                    <InputType 
                        type={props.options[key].type}
                        choice={props.options[key].choice}
                        values={props.options[key].values}
                        title={key}
                        input_change={props.input_change}
                    />
                </div>
              )
            })
          }
        </div>
    )
};

export default Inputs;