import React from 'react';
import PropTypes from 'prop-types';
import Icon from '../../../Common/Icon';


export default class BlockOutputListItem extends React.Component {
  static propTypes = {
    index: PropTypes.number.isRequired,
    item: PropTypes.shape({
      name: PropTypes.string.isRequired,
      file_type: PropTypes.string.isRequired,
      is_array: PropTypes.bool.isRequired,
    }).isRequired,
    onMouseDown: PropTypes.func.isRequired,
    onClick: PropTypes.func.isRequired,
    resources_dict: PropTypes.object.isRequired,
  }

  onMouseDown(e) {
    e.stopPropagation();
    e.preventDefault();
    this.props.onMouseDown(this.props.index);
  }

  onClick(e, displayRaw) {
    e.stopPropagation();
    e.preventDefault();
    console.log('oooooo', displayRaw);
    this.props.onClick(this.props.index, displayRaw);
  }

  render() {
    const type_descriptor = this.props.resources_dict[this.props.item.file_type];

    return (
      <li onMouseDown={(e) => this.onMouseDown(e)}
          onClick={(e) => this.onClick(e, type_descriptor.display_raw)}
          className="type_{this.props.item.file_type}">
        <div onClick={(e) => this.onClick(e, type_descriptor.display_raw)}>
          {this.props.item.name + (this.props.item.is_array ? '[...]' : '')}
          <Icon
            type_descriptor={type_descriptor}
          />
        </div>
      </li>
    );
  }
}
