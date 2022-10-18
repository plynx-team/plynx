import React from 'react';
import PropTypes from 'prop-types';
import BlockInputListItem from './BlockInputListItem';

export default class BlockInputList extends React.Component {
  static propTypes = {
    items: PropTypes.array.isRequired,
    onCompleteConnector: PropTypes.func.isRequired,
    resources_dict: PropTypes.object.isRequired,
  };

  onMouseUp(i) {
    this.props.onCompleteConnector(i);
  }

  render() {
    let i = 0;

    return (
      <div className="nodeInputWrapper">
        <ul className="nodeInputList">
          {this.props.items.map((item) => {
            return (
              <BlockInputListItem
                onMouseUp={(idx) => this.onMouseUp(idx)}
                key={i}
                index={i++}
                item={item}
                resources_dict={this.props.resources_dict}
              />
            );
          })}
        </ul>
      </div>
    );
  }
}
