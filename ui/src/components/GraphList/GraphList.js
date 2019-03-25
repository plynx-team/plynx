// src/components/About/index.js
import React, { Component } from 'react';
import GraphItem from './GraphItem.js'
import { listTextElement } from '../Common/listElements';
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
            user={graph._user[0]}
            />);

    return (
      <div className='list'>
        <div className='graph-list-item list-header'>
          { listTextElement('header-item', 'Header') }
          { listTextElement('header-item Status', 'Status') }
          { listTextElement('header-item Id', 'Graph ID') }
          { listTextElement('header-item Author', 'Author') }
          { listTextElement('header-item Created', 'Created') }
          { listTextElement('header-item Updated', 'Updated') }
        </div>
        {listItems}
      </div>
    );
  }
}
