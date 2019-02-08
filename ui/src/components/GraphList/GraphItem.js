// src/components/About/index.js
import React, { Component } from 'react';
import { listTextElement } from '../Common/listElements';
import './GraphItem.css';

export default class GraphItem extends Component {
  render() {
    return (
      <a className='list-item graph-list-item' href={'/graphs/' + this.props._id}>
        <div className='TitleDescription'>
          <div className='Title'>
            {this.props.title}
          </div>
          <div className='Description'>
            &ldquo;{this.props.description}&rdquo;
          </div>
        </div>

        { listTextElement('Status ' + this.props.graph_running_status, this.props.graph_running_status) }
        { listTextElement('Id', this.props._id) }
        { listTextElement('Created', this.props.insertion_date) }
        { listTextElement('Updated', this.props.update_date) }
      </a>
    );
  }
}
