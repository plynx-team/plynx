import React, { Component } from 'react';
import PropTypes from 'prop-types';

import './NodeItem.css';


export default class NodeItem extends Component {
  static propTypes = {
    node: PropTypes.object.isRequired,
  }

  render() {
    const node = this.props.node;
    return (
      <div className={`NodeItem node-${node._id}`}>
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
