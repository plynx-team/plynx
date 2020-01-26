import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import BaseList from '../BaseList';
import Controls from './Controls';
import { renderNodeItem, NODE_ITEM_HEADER } from './common';


const renderItem = renderNodeItem('nodes', 'node_status');

export default class ListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Operations - PLynx";
  }

  render() {
      console.log('aaa', renderItem);
    return (
        <div className="node-list-view">
            <Controls className="ControlButtons"
                      onCreateOperation={() => this.handleCreateOperation()}
                      onCreateGraph={() => this.handleCreateGraph()}

            />
            <BaseList
                menu={() => <a className="menu-button" href="/nodes/new">{"Create new Operation"}</a>}
                title="Operations - PLynx"
                tag="node-list-item"
                endpoint={PLynxApi.endpoints.search_nodes}
                extraSearch={{is_graph: false}}
                header={NODE_ITEM_HEADER}
                renderItem={renderItem}
            >
            </BaseList>
        </div>
    );
  }
}
