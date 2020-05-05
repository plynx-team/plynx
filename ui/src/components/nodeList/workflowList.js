import React, { Component } from 'react';
import BaseList from './baseList';
import { makeControlSeparator } from '../Common/controlButton';
import { COLLECTIONS, VIRTUAL_COLLECTIONS } from '../../constants';
import { renderNodeItem, NODE_ITEM_HEADER } from './common';


const renderItem = renderNodeItem(COLLECTIONS.TEMPLATES, 'node_status');

export default class WorkflowListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Workflows - PLynx";
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
                extraSearch={{virtual_collection: VIRTUAL_COLLECTIONS.WORKFLOWS}}
                header={NODE_ITEM_HEADER}
                renderItem={renderItem}
                virtualCollection={VIRTUAL_COLLECTIONS.WORKFLOWS}
                collection={COLLECTIONS.TEMPLATES}
            >
            </BaseList>
        </div>
    );
  }
}
