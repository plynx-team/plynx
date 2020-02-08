import React from 'react';
import SearchBar from './SearchBar';
import PropTypes from 'prop-types';


export function makeControlButton(props) {
  return (
    <div
       onClick={(e) => {
         e.preventDefault();
         if (props.enabled !== false) {
            props.func();
         }
       }}
       key={props.text}
       className={["control-button", (props.className || ''), (props.selected ? "selected" : ""), (props.enabled !== false ? 'enabled' : 'disabled')].join(" ")}
    >
       <img src={"/icons/" + props.img} alt={props.text}/>
       <div className='control-button-text'>{props.text}</div>
    </div>
  );
}

// TODO make a single function makeControlButton and makeControlLink
export function makeControlLink(props) {
  return (
    <a
       href={props.href}
       key={props.key}
       className={["control-button", (props.className || ''), (props.selected ? "selected" : ""), (props.enabled !== false ? 'enabled' : 'disabled')].join(" ")}
    >
       <img src={"/icons/" + props.img} alt={props.text}/>
       <div className='control-button-text'>{props.text}</div>
    </a>
  );
}

export function makeControlSeparator(props) {
    return (
        <div
            className='control-separator'
            key={props.key}
        />
    );
}

export function makeControlToggles(props) {
    return (
        <div
            className='control-toggle'
            key={props.key}
        >
            {props.items.map(
                (item, index) => {
                    if (index === props.index) {
                        item["selected"] = true;
                    }
                    item["key"] = index;
                    item.func = () => {
                        if (props.func) props.func(item.value);
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

export function makeControlSearchBar(props) {
    return <SearchBar
        onSearchUpdate={(search) => props.func(search)}
        search={props.search}
    />
}


export function makeControlPanel({props, children_func} = {}) {
    return (
        <div
            className='control-panel'
            key={props.key}
        >
            { children_func && children_func()  }
            {
                props.items.map(
                    (item) => {
                        return item.render(item.props);
                    }
                )
            }
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
