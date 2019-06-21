import React, { Component } from 'react';
import PropTypes from 'prop-types';
import NodeListItem from './NodeListItem';
import './style.css';

export default class NodeBarList extends Component {
  static propTypes = {
    items: PropTypes.array.isRequired,
  }

  render() {
    const listItems = this.props.items.map(
      (node) => <NodeListItem
        key={node._id}
        nodeContent={node}
        />);

    return (
      <div className="NodeBarList">
        {listItems }
      </div>
    );
  }
}
