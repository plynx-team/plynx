// src/components/About/index.js
import React, { Component } from 'react';
import GraphItem from './GraphItem.js'

import './style.css';


export default class GraphList extends Component {

  render() {
    const listItems = this.props.graphs.map(
          (graph) => <GraphItem
            _id={graph._id}
            title={graph.title}
            key={graph._id}
            description={graph.description ? graph.description : "No description"}
            insertion_date={graph.insertion_date}
            graph_running_status={graph.graph_running_status}
            />);

    return (
      <div className='List'>
        {listItems.length ? listItems : <b>No items to show</b>}
      </div>
    );
  }
}
