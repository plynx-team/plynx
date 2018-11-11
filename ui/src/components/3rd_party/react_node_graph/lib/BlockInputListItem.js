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
    let {name} = this.props.item;

    return (
      <li
        className={this.props.item.file_types[0]}
        >
        <a
          onClick={
            (e)=>this.noop(e)} onMouseUp={(e)=>this.onMouseUp(e)
          }
          href={null}
          >
          <img
            src={"/icons/file_types/" + this.props.item.file_types[0] + ".svg"}
            width="10"
            height="10"
            alt={this.props.item.file_types[0]}
            />
          {name}
        </a>
      </li>
    );
  }
}
