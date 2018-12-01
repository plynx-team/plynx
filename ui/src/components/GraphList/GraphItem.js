// src/components/About/index.js
import React, { Component } from 'react';
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
        <div className={'Id'}>{this.props._id}</div>
        <div className={'Status ' + this.props.graph_running_status}>{this.props.graph_running_status}</div>
        <div className='Created'>{this.props.insertion_date}</div>
      </a>
    );
  }
}
