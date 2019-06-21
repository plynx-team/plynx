import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { listTextElement } from '../Common/listElements';
import { NODE_STATUS } from '../../constants';
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

Item.propTypes = {
  _id: PropTypes.string,
  title: PropTypes.string,
  description: PropTypes.string,
  starred: PropTypes.bool,
  node_status: PropTypes.oneOf(Object.values(NODE_STATUS)),
  user: PropTypes.shape({
    username: PropTypes.string,
  }),
  insertion_date: PropTypes.string,
  update_date: PropTypes.string,
};
