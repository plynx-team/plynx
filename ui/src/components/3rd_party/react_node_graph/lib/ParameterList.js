import React from 'react';
import PropTypes from 'prop-types';
import ParameterListItem from './ParameterListItem';


export default class ParameterList extends React.Component {
  static propTypes = {
    items: PropTypes.array.isRequired,
    onClick: PropTypes.func.isRequired,
  }

  onMouseUp(i) {
    this.props.onClick(i);
  }

  render() {
    let i = 0;

    // TODO broken: this.props.items is null
    return (
      <div className="nodeParameterWrapper">
          {this.props.items && this.props.items.map((item) => {
            return (
              <ParameterListItem onMouseUp={(i) => this.onMouseUp(i)} key={i} index={i++} item={item} /> // eslint-disable-line no-shadow
            );
          })}
      </div>
    );
  }
}
