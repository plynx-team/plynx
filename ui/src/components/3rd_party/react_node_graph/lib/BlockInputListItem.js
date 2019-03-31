import React from 'react';
import PropTypes from 'prop-types';


export default class BlockInputListItem extends React.Component {
  static propTypes = {
    index: PropTypes.number.isRequired,
    item: PropTypes.shape({
      name: PropTypes.string.isRequired,
      file_types: PropTypes.array.isRequired,
    }).isRequired,
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
    const {name} = this.props.item;

    return (
      <li
        className={this.props.item.file_types[0]}
        >
        <a
          onClick={
            (e) => this.noop(e)} onMouseUp={(e) => this.onMouseUp(e)
          }
          href={null}
          >
          <img
            src={"/icons/file_types/" + this.props.item.file_types[0] + ".svg"}
            width="10"
            height="10"
            alt={this.props.item.file_types[0]}
            />
          {name}
        </a>
      </li>
    );
  }
}
