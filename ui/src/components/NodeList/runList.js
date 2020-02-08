import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import BaseList from './baseList';
import Controls from './Controls';
import { COLLECTIONS } from '../../constants';
import { renderNodeItem, NODE_ITEM_HEADER } from './common';


const renderItem = renderNodeItem(COLLECTIONS.RUNS, 'node_running_status');

export default class ListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Runs - PLynx";
  }

  render() {
    return (
        <div className="node-list-view">
            {this.props.showControlls &&
                <Controls className="ControlButtons"
                          onCreateOperation={() => this.handleCreateOperation()}
                          onCreateGraph={() => this.handleCreateGraph()}

                />
            }
            <BaseList
                menu={() => <a className="menu-button" href={`/${COLLECTIONS.TEMPLATES}/new`}>{"Create new Operation"}</a>}
                title="Operations - PLynx"
                tag="node-list-item"
                endpoint={PLynxApi.endpoints[`search_${COLLECTIONS.RUNS}`]}
                search={this.props.search}
                extraSearch={{is_graph: false}}
                header={NODE_ITEM_HEADER}
                renderItem={renderItem}
            >
            </BaseList>
        </div>
    );
  }
}
