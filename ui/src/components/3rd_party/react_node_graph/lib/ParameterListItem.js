import React from 'react';
import PropTypes from 'prop-types';


export default class BlockInputListItem extends React.Component {
  static propTypes = {
    index: PropTypes.number.isRequired,
    item: PropTypes.string.isRequired,
    onMouseUp: PropTypes.func.isRequired,
  }

  onMouseUp(e) {
    e.stopPropagation();
    e.preventDefault();

    this.props.onMouseUp(this.props.index);
  }

  noop(e) {
    e.stopPropagation();
    e.preventDefault();
  }

  render() {
    const name = this.props.item;

    return (
      <div className="parameterItem">
        <div
          className="button"
          onClick={
            (e) => this.noop(e)} onMouseUp={(e) => this.onMouseUp(e)
          }
          >
          {name}
        </div>
      </div>
    );
  }
}
