import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import BaseList from './baseList';
import { makeControlSeparator, makeControlLink } from '../Common/controlButton';
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
    {
      render: makeControlLink,
      props: {
          img: 'plus.svg',
          text: 'Create new Group',
          href: `/groups/_GROUP`,
          key: 'new group'
        },
    },
  ];

  render() {
    return (
        <div className="node-list-view">
            <BaseList
                menuPanelDescriptor={this.MENU_PANEL_DESCRIPTOR}
                tag="node-list-item"
                endpoint={PLynxApi.endpoints[`search_${COLLECTIONS.GROUPS}`]}
                header={GROUP_ITEM_HEADER}
                renderItem={renderItem}

            >
            </BaseList>
        </div>
    );
  }
}
