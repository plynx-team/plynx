import React, { Component } from 'react';
import PropTypes from 'prop-types';
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
        { listTextElement('Author', this.props.user.username) }
        { listTextElement('Created', this.props.insertion_date) }
        { listTextElement('Updated', this.props.update_date) }
      </a>
    );
  }
}

GraphItem.propTypes = {
  graphs: PropTypes.array,
  _id: PropTypes.string,
  title: PropTypes.string,
  description: PropTypes.string,
  graph_running_status: PropTypes.string,
  user: PropTypes.shape({
    username: PropTypes.string,
  }),
  insertion_date: PropTypes.string,
  update_date: PropTypes.string,
};
