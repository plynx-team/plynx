import React from 'react';
import PropTypes from 'prop-types';
import BlockOutputListItem from './BlockOutputListItem';


export default class BlockOutputList extends React.Component {
  static propTypes = {
    items: PropTypes.array.isRequired,
    onStartConnector: PropTypes.func.isRequired,
    onClick: PropTypes.func.isRequired,
  }

  onMouseDown(i) {
    this.props.onStartConnector(i);
  }

  onClick(i) {
    this.props.onClick(i);
  }

  render() {
    let i = 0;

    return (
      <div className="nodeOutputWrapper">
          <ul className="nodeOutputList">
          {this.props.items.map((item) => {
            return (
              <BlockOutputListItem onMouseDown={(i) => this.onMouseDown(i)}     // eslint-disable-line no-shadow
                                  onClick={(i) => this.onClick(i)}              // eslint-disable-line no-shadow
                                  key={i}                                       // eslint-disable-line no-shadow
                                  index={i++}                                   // eslint-disable-line no-shadow
                                  item={item} />
            );
          })}
        </ul>
      </div>
    );
  }
}
