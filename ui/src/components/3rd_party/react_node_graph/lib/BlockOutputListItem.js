import React from 'react';

export default class BlockOutputListItem extends React.Component {

  onMouseDown(e) {
    e.stopPropagation();
    e.preventDefault();
    this.props.onMouseDown(this.props.index);
  }

  onClick(e) {
    e.stopPropagation();
    e.preventDefault();
    this.props.onClick(this.props.index);
  }

  render() {
    return (
      <li onMouseDown={(e)=>this.onMouseDown(e)}
          onClick={(e)=>this.onClick(e)}
          className={this.props.item.file_type}>
        <a href={null} onClick={(e)=>this.onClick(e)}>
          {this.props.item.name}
          <img
            src={"/icons/file_types/" + this.props.item.file_type + ".svg"}
            width="10"
            height="10"
            alt="*"
            />
        </a>
      </li>
    );
  }
}
