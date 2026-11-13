import React from 'react';
import { PluginsConsumer } from '../../contexts';
import Icon from '../Common/Icon';
import { listTextElement, renderStatus } from '../Common/ListElements';
import { utcTimeToLocal } from '../../utils';
import { NodeData, PluginsDict } from '../../types';
import '../controls.css';
import './items.css';

export function getAuthorText(node: NodeData): string {
  if (node._user && node._user.length > 0) {
    if (node._user[0].settings && node._user[0].settings.display_name) {
      return node._user[0].settings.display_name;
    }
    return node._user[0].username || 'Unknown';
  }
  return 'Unknown';
}

export function renderNodeItem(hrefPrefix: string, statusName: string) {
  return (node: NodeData) => (
    <a href={`/${hrefPrefix}/${node._id}`} key={node._id} className="list-item-link">
      <PluginsConsumer>
        {(plugins_dict: PluginsDict) => {
          const executor = plugins_dict.executors_info?.[node.kind];
          return (
            <div className="list-item node-list-item">
              {listTextElement('Title', node.title)}
              {listTextElement(`Status ${node[statusName]}`, renderStatus(node[statusName]))}
              {listTextElement('Id', node._id)}
              <div className="Type node-type">
                {executor && (
                  <Icon
                    type_descriptor={executor}
                    className="operation-icon"
                  />
                )}
                <div className="operation-title-text">
                  {executor ? executor.title : node.kind}
                </div>
              </div>
              {listTextElement('Author', getAuthorText(node))}
              {listTextElement('Created', utcTimeToLocal(node.insertion_date))}
              {listTextElement('Updated', utcTimeToLocal(node.update_date))}
            </div>
          );
        }}
      </PluginsConsumer>
    </a>
  );
}

export function renderGroupItem(hrefPrefix: string) {
  return (node: NodeData) => (
    <a href={`/${hrefPrefix}/${node._id}`} key={node._id} className="list-item-link">
      <div className="list-item node-list-item">
        {listTextElement('Title', node.title)}
        <div className="Type node-type">
          <Icon
            type_descriptor={{ icon: 'feathericons.layers', color: '#2af' }}
            className="operation-icon"
          />
          <div className="operation-title-text">Group</div>
        </div>
        {listTextElement('Id', node._id)}
        {listTextElement('Author', node._user && node._user.length > 0 ? node._user[0].username : 'Unknown')}
        {listTextElement('Created', utcTimeToLocal(node.insertion_date))}
        {listTextElement('Updated', utcTimeToLocal(node.update_date))}
      </div>
    </a>
  );
}

export const NODE_ITEM_HEADER = [
  { title: 'Header', tag: '' },
  { title: 'Status', tag: 'Status' },
  { title: 'Node Id', tag: 'Id' },
  { title: 'Type', tag: 'Type' },
  { title: 'Author', tag: 'Author' },
  { title: 'Created', tag: 'Created' },
  { title: 'Updated', tag: 'Updated' },
];

export const GROUP_ITEM_HEADER = [
  { title: 'Title', tag: '' },
  { title: 'Type', tag: 'Type' },
  { title: 'Group Id', tag: 'Id' },
  { title: 'Author', tag: 'Author' },
  { title: 'Created', tag: 'Created' },
  { title: 'Updated', tag: 'Updated' },
];
