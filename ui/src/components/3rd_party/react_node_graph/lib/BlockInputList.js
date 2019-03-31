import React from 'react';
import PropTypes from 'prop-types';
import BlockInputListItem from './BlockInputListItem';


export default class BlockInputList extends React.Component {
  static propTypes = {
    items: PropTypes.array.isRequired,
    onCompleteConnector: PropTypes.func.isRequired,
  }

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
              <BlockInputListItem onMouseUp={(i) => this.onMouseUp(i)} key={i} index={i++} item={item} />   // eslint-disable-line no-shadow
            );
          })}
        </ul>
      </div>
    );
  }
}
