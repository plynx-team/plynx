import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { listTextElement } from '../Common/listElements';


export default class List extends Component {
  render() {

    const headerItems = this.props.header.map(
        (headerDescriptor) => listTextElement('header-item ' + headerDescriptor.tag, headerDescriptor.title, headerDescriptor.title)
    );
    const listItems = this.props.items.map(
      (node) => this.props.renderItem(node)
    );

    return (
      <div className='list'>
        <div className='node-list-item list-header'>
          {headerItems}
        </div>
        {listItems}
      </div>
    );
  }
}

List.propTypes = {
  nodes: PropTypes.array,
};
