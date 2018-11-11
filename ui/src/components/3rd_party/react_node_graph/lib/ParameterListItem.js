import React from 'react';

export default class BlockInputListItem extends React.Component {
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
    let name = this.props.item;

    return (
      <div className="parameterItem">
        <a
          className="button"
          onClick={
            (e)=>this.noop(e)} onMouseUp={(e)=>this.onMouseUp(e)
          }
          href={null}
          >
          {name}
        </a>
      </div>
    );
  }
}
