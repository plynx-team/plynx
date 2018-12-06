// src/components/About/index.js
import React, { Component } from 'react';
import GraphItem from './GraphItem.js'
import '../Common/List.css';
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
            update_date={graph.update_date}
            />);

    return (
      <div className='list'>
        <div className='graph-list-item list-header'>
          <div className='header-item'>Header</div>
          <div className='header-item'>Graph ID</div>
          <div className='header-item'>Status</div>
          <div className='header-item'>Created</div>
          <div className='header-item'>Updated</div>
        </div>
        {listItems.length ? listItems : <b>No items to show</b>}
      </div>
    );
  }
}
