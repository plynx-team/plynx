import React from 'react';
import PropTypes from 'prop-types';


export default function makeControlButton(props) {
  return (
    <div
       onClick={(e) => {
         e.preventDefault();
         props.func();
       }}
       className={"control-button " + (props.className || '')}>
       <img src={"/icons/" + props.img} alt={props.text}/>
       <div className='control-button-text'>{props.text}</div>
    </div>
  );
}

makeControlButton.propTypes = {
  func: PropTypes.func.isRequired,
  className: PropTypes.string,
  img: PropTypes.string.isRequired,
  text: PropTypes.string.isRequired,
};
