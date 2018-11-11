import React from 'react';

import BlockOutputListItem from './BlockOutputListItem';

export default class BlockOutputList extends React.Component {

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
              <BlockOutputListItem onMouseDown={(i)=>this.onMouseDown(i)}
                                  onClick={(i)=>this.onClick(i)}
                                  key={i}
                                  index={i++}
                                  item={item} />
            )
          })}
        </ul>
      </div>
    );
  }
}
