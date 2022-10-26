import React from 'react';
import PropTypes from 'prop-types';
import ThumbnailListItem from './ThumbnailListItem';

export default class ThumbnailList extends React.Component {
  static propTypes = {
    items: PropTypes.array.isRequired,
    onClick: PropTypes.func.isRequired,
    resources_dict: PropTypes.object.isRequired,
  };

  render() {
    let i = 0;

    // TODO broken: this.props.items is null
    return (
      <div className="node-thumbnail-wrapper">
        <div className="node-separator"></div>
          {this.props.items && this.props.items.map((item) => {
            return (
              <ThumbnailListItem
                onClick={this.props.onClick}
                key={i}
                index={i++}
                item={item}
                resources_dict={this.props.resources_dict}
              /> // eslint-disable-line no-shadow
            );
          })}
      </div>
    );
  }
}
