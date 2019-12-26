import React from 'react';
import PropTypes from 'prop-types';


export function makeControlButton(props) {
  return (
    <div
       onClick={(e) => {
         e.preventDefault();
         props.func();
       }}
       key={props.key}
       className={["control-button", (props.className || ''), (props.selected ? "selected" : "")].join(" ")}
    >
       <img src={"/icons/" + props.img} alt={props.text}/>
       <div className='control-button-text'>{props.text}</div>
    </div>
  );
}

export function makeControlToggles(props) {
    return (
        <div className='control-toggle'>
        {props.items.map(
            (item, index) => {
                if (index === props.index) {
                    item["selected"] = true;
                }
                item["key"] = index;
                item.func = () => {
                    props.func(item.value);
                    props.onIndexChange(index);
                }
                if (index === 0) {
                    item['className'] = 'first';
                }
                if (index === props.items.length - 1) {
                    item['className'] = 'last';
                }

                return makeControlButton(item);
            }
        )}
        </div>
    );
}

makeControlButton.propTypes = {
  func: PropTypes.func.isRequired,
  className: PropTypes.string,
  img: PropTypes.string.isRequired,
  text: PropTypes.string.isRequired,
  selected: PropTypes.bool,
  key: PropTypes.number,
};
