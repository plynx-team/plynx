import React from 'react';
import {PluginsConsumer} from '../../contexts';
import Icon from '../Common/Icon';
import { listTextElement, renderStatus } from '../Common/listElements';
import { utcTimeToLocal } from '../../utils';
import '../controls.css';
import './items.css';


function getAuthorText(node) {
  if (node._user.length > 0) {
    if (node._user[0].settings && node._user[0].settings.display_name) {
      return node._user[0].settings.display_name;
    }
    return node._user[0].username;
  }
  return 'Unknown';
}


export function renderNodeItem(hrefPrefix, statusName) {
  return (node) => {
    return (
       <a
                href={'/' + hrefPrefix + '/' + node._id}
                key={node._id}
                className='list-item-link'
                >
        <PluginsConsumer>
        {
          plugins_dict => <div className='list-item node-list-item'>
            { listTextElement('Title', node.title) }
            { listTextElement(`Status ${node[statusName]}`, renderStatus(node[statusName])) }
            { listTextElement('Id', node._id) }
            <div className='Type node-type'>
                <Icon
                  type_descriptor={plugins_dict.executors_info[node.kind]}
                  className="operation-icon"
                />
                <div className="operation-title-text">
                  {plugins_dict.executors_info[node.kind].title}
                </div>
            </div>
            { listTextElement('Author', getAuthorText(node)) }
            { listTextElement('Created', utcTimeToLocal(node.insertion_date)) }
            { listTextElement('Updated', utcTimeToLocal(node.update_date)) }
        </div>
    }
    </PluginsConsumer>
        </a>);
  };
}

export function renderGroupItem(hrefPrefix) {
  return (node) => {
    return (
       <a
                href={'/' + hrefPrefix + '/' + node._id}
                key={node._id}
                className='list-item-link'
                >
          <div className='list-item node-list-item'>
            { listTextElement('Title', node.title) }
            <div className='Type node-type'>
                <Icon
                  type_descriptor={{icon: "feathericons.layers", color: "#2af"}}
                  className="operation-icon"
                />
                <div className="operation-title-text">
                  Group
                </div>
            </div>
            { listTextElement('Id', node._id) }
            { listTextElement('Author', node._user.length > 0 ? node._user[0].username : 'Unknown') }
            { listTextElement('Created', utcTimeToLocal(node.insertion_date)) }
            { listTextElement('Updated', utcTimeToLocal(node.update_date)) }
          </div>
        </a>);
  };
}

export const NODE_ITEM_HEADER = [
   {title: "Header", tag: ""},
   {title: "Status", tag: "Status"},
   {title: "Node Id", tag: "Id"},
   {title: "Type", tag: "Type"},
   {title: "Author", tag: "Author"},
   {title: "Created", tag: "Created"},
   {title: "Updated", tag: "Updated"},
];

export const GROUP_ITEM_HEADER = [
   {title: "Title", tag: ""},
   {title: "Type", tag: "Type"},
   {title: "Group Id", tag: "Id"},
   {title: "Author", tag: "Author"},
   {title: "Created", tag: "Created"},
   {title: "Updated", tag: "Updated"},
];
