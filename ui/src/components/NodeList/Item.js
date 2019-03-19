import React, { Component } from 'react';
import { listTextElement } from '../Common/listElements';
import './Item.css';

export default class Item extends Component {
  render() {
    return (
      <a className='list-item node-list-item' href={'/nodes/' + this.props._id}>
        <div className='ItemHeader'>
          <div className='TitleDescription'>
            <div className='Title'>
              {this.props.title}
            </div>
            <div className='Description'>
              &ldquo;{this.props.description}&rdquo;
            </div>
          </div>
          <div className={this.props.starred ? 'star-visible' : 'star-hidden'}>
            <img src="/icons/star.svg" alt="star" />
          </div>
        </div>

        { listTextElement('Status ' + this.props.node_status, this.props.node_status) }
        { listTextElement('Id', this.props._id) }
        { listTextElement('Author', this.props.user.username) }
        { listTextElement('Created', this.props.insertion_date) }
        { listTextElement('Updated', this.props.update_date) }
      </a>
    );
  }
}
