import React, { Component } from 'react';
import Item from './Item.js'
import { listTextElement } from '../Common/listElements';

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
        update_date={node.update_date}
        node_running_status={node.node_running_status}
        node_status={node.node_status}
        />);

    return (
      <div className='list'>
        <div className='node-list-item list-header'>
          { listTextElement('header-item', 'Header') }
          { listTextElement('header-item Status', 'Status') }
          { listTextElement('header-item Id', 'Node Id') }
          { listTextElement('header-item Created', 'Created') }
          { listTextElement('header-item Updated', 'Updated') }
        </div>
        {listItems}
      </div>
    );
  }
}
