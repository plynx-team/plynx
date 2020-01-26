import React, { Component } from 'react';
import {PluginsConsumer} from '../../contexts';
import { listTextElement } from '../Common/listElements';
import '../Common/ListPage.css';
import '../controls.css';
import './items.css';

export function renderNodeItem(hrefPrefix, statusName) {
    return (node) => {
      return (
          <a className='list-item node-list-item'
            href={'/' + hrefPrefix +'/' + node._id}
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

            { listTextElement('Status ' + node[statusName], node[statusName]) }
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
}

export const NODE_ITEM_HEADER = [
   {title: "Header", tag: ""},
   {title: "Status", tag: "Status"},
   {title: "Node Id", tag: "Id"},
   {title: "Kind", tag: "Kind"},
   {title: "Type", tag: "Type"},
   {title: "Author", tag: "Author"},
   {title: "Created", tag: "Created"},
   {title: "Updated", tag: "Updated"},
];
