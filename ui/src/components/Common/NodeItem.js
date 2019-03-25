// src/components/About/index.js
import React, { Component } from 'react';

import './NodeItem.css';


export default class NodeItem extends Component {
  render() {
    let node = this.props.node;
    return (
      <div className={'NodeItem' + (node.base_node_name === 'file' ? ' File' : '')}>
        <div className='NodeHeader'>
          <div className='NodeTitle'>
            {node.title}
          </div>
        </div>
        <div className='NodeDescription'>
          <div className="description-text">
            &ldquo;{node.description}&rdquo;
          </div>
          <div className={node.starred ? 'star-visible' : 'star-hidden'}>
            <img src="/icons/star.svg" alt="star" />
          </div>
        </div>
      </div>
    );
  }
}
