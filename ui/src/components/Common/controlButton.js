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
       className={[
         "control-button",
           (props.className || ''),
           (props.selected ? "selected" : ""),
           (props.enabled !== false ? 'enabled' : 'disabled')
       ].join(" ")}
    >
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
  selected: PropTypes.bool,
  key: PropTypes.number,
  enabled: PropTypes.bool.isRequired,
  extraClassName: PropTypes.object,
};


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

makeControlLink.propTypes = {
  href: PropTypes.string.isRequired,
  key: PropTypes.number,
  className: PropTypes.string,
  img: PropTypes.string.isRequired,
  text: PropTypes.string.isRequired,
  selected: PropTypes.bool,
  enabled: PropTypes.bool.isRequired,
};


export function makeControlSeparator(props) {
  return (
        <div
            className='control-separator'
            key={props.key}
        />
  );
}

makeControlSeparator.propTypes = {
  key: PropTypes.string.isRequired,
};


export function makeControlToggles(props) {
  return (
        <div
            className='control-toggle'
            key={props.key}
        >
            {props.items.map(
                (item, index) => {
                  const buttonItem = Object.assign({}, item);
                  if (index === props.index) {
                    buttonItem["selected"] = true;
                  }
                  buttonItem["key"] = index;
                  buttonItem.func = () => {
                    if (props.func) {
                      props.func(item.value);
                    }
                    props.onIndexChange(index);
                  };
                  if (index === 0) {
                    buttonItem['className'] = 'first';
                  }
                  if (index === props.items.length - 1) {
                    buttonItem['className'] = 'last';
                  }

                  return makeControlButton(buttonItem);
                }
            )}
        </div>
  );
}

makeControlToggles.propTypes = {
  key: PropTypes.string.isRequired,
  items: PropTypes.arrayOf(
      PropTypes.shape({
        index: PropTypes.number.isRequired,
      })
  ).isRequired,
  func: PropTypes.func,
  onIndexChange: PropTypes.func.isRequired,
  index: PropTypes.number.isRequired,
};


export function makeControlSearchBar(props) {
  return <SearchBar
        onSearchUpdate={(search) => props.func(search)}
        search={props.search}
    />;
}

makeControlSearchBar.propTypes = {
  func: PropTypes.func.isRequired,
  search: PropTypes.string.isRequired,
};


export function makeControlPanel({props, children_func} = {}) {
  return (
        <div
            className='control-panel'
            key={props.key}
        >
            { children_func && children_func() }
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

makeControlPanel.propTypes = {
  props: PropTypes.shape({
    key: PropTypes.string.isRequired,
  }),
  key: PropTypes.string.isRequired,
  items: PropTypes.arrayOf(
      PropTypes.shape({
        render: PropTypes.func.isRequired,
        props: PropTypes.object.isRequired,
      })
  ).isRequired,
  children_func: PropTypes.func,
};
