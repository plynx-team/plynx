import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import BaseList from '../BaseList';
import {PluginsConsumer} from '../../contexts';
import { listTextElement } from '../Common/listElements';
import '../Common/ListPage.css';
import '../controls.css';
import './items.css';


function renderItem(node) {
    console.log(node);
  return (
      <a className='list-item node-list-item'
        href={'/nodes/' + node._id}
        key={node._id}
        >
        <div className='ItemHeader'>
          <div className='TitleDescription'>
            <div className='Title'>
              {node.title}
            </div>
            <div className='Description'>
              &ldquo;{node.description}&rdquo;
            </div>
          </div>
          <div className={node.starred ? 'star-visible' : 'star-hidden'}>
            <img src="/icons/star.svg" alt="star" />
          </div>
        </div>

        { listTextElement('Status ' + node.node_status, node.node_status) }
        { listTextElement('Id', node._id) }
        <PluginsConsumer>
            { plugins_info => listTextElement('Kind', plugins_info.executors_info[node.kind].alias)}
        </PluginsConsumer>
        <PluginsConsumer>
            { plugins_info => listTextElement('Type', plugins_info.executors_info[node.kind].is_graph ? "Graph": "Operation")}
        </PluginsConsumer>
        { listTextElement('Author', node._user.length > 0 ? node._user[0].username : 'Unknown') }
        { listTextElement('Created', node.insertion_date) }
        { listTextElement('Updated', node.update_date) }
      </a>
  );
}


export default class ListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Operations - PLynx";
  }

  render() {
    const header = [
       {title: "Header", tag: ""},
       {title: "Status", tag: "Status"},
       {title: "Node Id", tag: "Id"},
       {title: "Kind", tag: "Kind"},
       {title: "Type", tag: "Type"},
       {title: "Author", tag: "Author"},
       {title: "Created", tag: "Created"},
       {title: "Updated", tag: "Updated"},
    ];
    return (
        <BaseList
            menu={() => <a className="menu-button" href="/nodes/new">{"Create new Operation"}</a>}
            title="Operations - PLynx"
            tag="node-list-item"
            endpoint={PLynxApi.endpoints.search_nodes}
            extraSearch={{is_graph: false}}
            header={header}
            renderItem={renderItem}
        >
        </BaseList>
    );
  }
}
