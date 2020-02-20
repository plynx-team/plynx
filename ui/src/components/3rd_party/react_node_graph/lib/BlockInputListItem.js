import React from 'react';
import PropTypes from 'prop-types';
import Icon from '../../../Common/Icon';


export default class BlockInputListItem extends React.Component {
  static propTypes = {
    index: PropTypes.number.isRequired,
    item: PropTypes.shape({
      name: PropTypes.string.isRequired,
      file_type: PropTypes.string.isRequired,
      is_array: PropTypes.bool.isRequired,
    }).isRequired,
    onMouseUp: PropTypes.func.isRequired,
    resources_dict: PropTypes.object.isRequired,
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
    const type_descriptor = this.props.resources_dict[this.props.item.file_type];

    return (
      <li
        className={this.props.item.file_type}
        >
        <div
          onClick={
            (e) => this.noop(e)} onMouseUp={(e) => this.onMouseUp(e)
          }
          >
          <Icon
            type_descriptor={type_descriptor}
          />
          {this.props.item.name + (this.props.item.is_array ? '[...]' : '')}
        </div>
      </li>
    );
  }
}
