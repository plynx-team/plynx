// src/components/About/index.js
import React, { Component } from 'react';
import NodeListItem from './NodeListItem.js'
import './style.css';

export default class NodeBarList extends Component {
  render() {
    const listItems = this.props.items.map(
      (node) => <NodeListItem
        key={node._id}
        nodeContent={node}
        />);

    return (
      <div className="NodeBarList">
        {listItems }
      </div>
    );
  }
}
