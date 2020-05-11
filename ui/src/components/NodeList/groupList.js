import React, { Component } from 'react';
import BaseList from './baseList';
import { makeControlSeparator } from '../Common/controlButton';
import { COLLECTIONS, VIRTUAL_COLLECTIONS } from '../../constants';
import { renderGroupItem, GROUP_ITEM_HEADER } from './common';


const renderItem = renderGroupItem(COLLECTIONS.GROUPS);

export default class GroupListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Groups - PLynx";
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
                header={GROUP_ITEM_HEADER}
                renderItem={renderItem}
                virtualCollection={VIRTUAL_COLLECTIONS.WORKFLOWS}
                collection={COLLECTIONS.GROUPS}
            >
            </BaseList>
        </div>
    );
  }
}
