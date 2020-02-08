import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import BaseList from './baseList';
import { makeControlPanel, makeControlToggles, makeControlLink, makeControlButton, makeControlSeparator, makeControlSearchBar } from '../Common/controlButton';
import { COLLECTIONS } from '../../constants';
import { renderNodeItem, NODE_ITEM_HEADER } from './common';


const renderItem = renderNodeItem(COLLECTIONS.TEMPLATES, 'node_status');

export default class ListPage extends Component {
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
                endpoint={PLynxApi.endpoints[`search_${COLLECTIONS.TEMPLATES}`]}
                extraSearch={{is_graph: false}}
                header={NODE_ITEM_HEADER}
                renderItem={renderItem}
                pluginsDictMenuTransformer={(plugins_dict) => Object.values(plugins_dict.workflows_dict).map(
                    (operation) => {
                        console.log(operation);
                        return {
                            render: makeControlLink,
                            props: {
                              img: 'plus.svg',
                              text: operation.title,
                              href: `/templates/${operation.kind}`,
                              key: operation.kind
                            },
                        };
                    }
                )}
            >
            </BaseList>
        </div>
    );
  }
}
