import React from 'react';
import PropTypes from 'prop-types';

export default class ThumbnailListItem extends React.Component {
  static propTypes = {
    index: PropTypes.number.isRequired,
    item: PropTypes.shape({
      name: PropTypes.string.isRequired,
      file_type: PropTypes.string.isRequired,
      is_array: PropTypes.bool.isRequired,
      thumbnail:  PropTypes.string.isRequired,
    }).isRequired,
    resources_dict: PropTypes.object.isRequired,
  };

  noop(e) {
    e.stopPropagation();
    e.preventDefault();
  }

  render() {
    const name = this.props.item.name;

    return (
      <div
        className="parameterItem"
        onClick={
          (e) => {
              this.noop(e);
              const type_descriptor = this.props.resources_dict[this.props.item.file_type];
              this.props.onClick(this.props.item.name, type_descriptor.display_raw)
          }
        }
        >
          <div
            className="item-title"
            >
            {name}
          </div>
          <div
            dangerouslySetInnerHTML={{ __html: this.props.item.thumbnail }}           // eslint-disable-line react/no-danger
          />
        </div>
    );
  }
}
