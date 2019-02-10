import React from 'react';


export default function makeControlButton(props) {
  return (
    <a href={null}
       onClick={(e) => {e.preventDefault(); props.func();}}
       className={"control-button " + (props.className || '')}>
       <img src={"/icons/" + props.img} alt={props.text}/>
       <div className='control-button-text'>{props.text}</div>
    </a>
  );
}
