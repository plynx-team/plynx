// src/components/About/index.js
import React, { Component } from 'react';
import Item from './Item.js'

import './style.css';


export default class List extends Component {
  render() {
    const listItems = this.props.nodes.map(
      (node) => <Item
        _id={node._id}
        title={node.title}
        key={node._id}
        description={node.description ? node.description : "No description"}
        insertion_date={node.insertion_date}
        node_running_status={node.node_running_status}
        node_status={node.node_status}
        />);

    return (
      <div className='List'>
        {listItems.length ? listItems : <b>No items to show</b>}
      </div>
    );
  }
}
