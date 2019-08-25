import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import BaseList from '../BaseList';
import { OPERATIONS } from '../../constants';
import { listTextElement } from '../Common/listElements';
import '../Common/ListPage.css';
import '../controls.css';
import './items.css';


function renderItem(node) {
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
        { listTextElement('Author', node._user[0].username) }
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
            extraSearch={{base_node_names: OPERATIONS}}
            header={header}
            renderItem={renderItem}
        >
        </BaseList>
    );
  }
}
