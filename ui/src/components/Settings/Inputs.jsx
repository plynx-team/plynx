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
            props.options.map((option) => {
              return (
                <div className='option-cell' key={option.title}>
                    <div className='cell-title'>{option.title}</div>
                    <InputType 
                        type={option.type}
                        choice={option.choice}
                        values={option.values}
                        title={option.title}
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