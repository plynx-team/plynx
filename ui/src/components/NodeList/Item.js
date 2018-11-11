// src/components/About/index.js
import React, { Component } from 'react';
import './Item.css';

export default class Item extends Component {
  render() {
    return (
      <a className='NodeListItem' href={'/nodes/' + this.props._id}>
        <div className='TitleDescription'>
          <div className='Title'>
            {this.props.title}
          </div>
          <div className='Description'>
            &ldquo;{this.props.description}&rdquo;
          </div>
        </div>
        <div className={'Id'}>{this.props._id}</div>
        <div className={'Status ' + this.props.node_status}>{this.props.node_status}</div>
        <div className='Created'>{this.props.insertion_date}</div>
      </a>
    );
  }
}
