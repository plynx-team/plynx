import React, { Component } from 'react';
import PropTypes from 'prop-types';
import HubEntryListItem from './HubEntryListItem';
import './style.css';

export default class HubEntryList extends Component {
  static propTypes = {
    items: PropTypes.array.isRequired,
  }

  render() {
    const listItems = this.props.items.map(
      (node) => <HubEntryListItem
        key={node._id}
        nodeContent={node}
        />);

    return (
      <div className="hub-entry-list">
        {listItems }
      </div>
    );
  }
}
