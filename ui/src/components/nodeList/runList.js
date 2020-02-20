import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { PLynxApi } from '../../API';
import BaseList from './baseList';
import { makeControlSeparator } from '../Common/controlButton';
import { COLLECTIONS } from '../../constants';
import { renderNodeItem, NODE_ITEM_HEADER } from './common';


const renderItem = renderNodeItem(COLLECTIONS.RUNS, 'node_running_status');

export default class RunListPage extends Component {
  static propTypes = {
    search: PropTypes.string,
  }

  constructor(props) {
    super(props);
    document.title = "Runs - PLynx";
  }

  MENU_PANEL_DESCRIPTOR = [
    {
      render: makeControlSeparator,
      props: {key: 'separator_1'}
    },
  ];

  render() {
    return (
        <div className="node-list-view">
            <BaseList
                menuPanelDescriptor={this.MENU_PANEL_DESCRIPTOR}
                tag="node-list-item"
                endpoint={PLynxApi.endpoints[`search_${COLLECTIONS.RUNS}`]}
                header={NODE_ITEM_HEADER}
                search={this.props.search}
                renderItem={renderItem}
            >
            </BaseList>
        </div>
    );
  }
}
