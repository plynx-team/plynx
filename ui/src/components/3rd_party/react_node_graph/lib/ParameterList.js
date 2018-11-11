import React from 'react';

import ParameterListItem from './ParameterListItem';

export default class ParameterList extends React.Component {

  onMouseUp(i) {
    this.props.onClick(i);
  }

  render() {
    let i = 0;

    return (
      <div className="nodeParameterWrapper">
          {this.props.items.map((item) => {
            return (
              <ParameterListItem onMouseUp={(i)=>this.onMouseUp(i)} key={i} index={i++} item={item} />
            )
          })}
      </div>
    );
  }
}
