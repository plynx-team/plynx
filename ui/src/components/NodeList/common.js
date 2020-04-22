import React from 'react';
import {PluginsConsumer} from '../../contexts';
import Icon from '../Common/Icon';
import { listTextElement, renderStatus } from '../Common/listElements';
import { utcTimeToLocal } from '../../utils';
import '../controls.css';
import './items.css';

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
            <div className='ItemHeader'>
              <div className='TitleDescription'>

                <div className='node-header-title'>
                    <Icon
                      type_descriptor={plugins_dict.executors_info[node.kind]}
                      className="operation-icon"
                    />
                    <div className="operation-title-text">
                      {plugins_dict.executors_info[node.kind].title}
                    </div>
                </div>
                <div className='Title'>
                  {node.title}
                </div>
              </div>
              <div className={node.starred ? 'star-visible' : 'star-hidden'}>
                <img src="/icons/star.svg" alt="star" />
              </div>
            </div>

            { listTextElement(`Status ${node[statusName]}`, renderStatus(node[statusName])) }
            { listTextElement('Id', node._id) }
            { listTextElement(
                'Type',
                    plugins_dict.operations_dict[node.kind] ? plugins_dict.operations_dict[node.kind].title :
                    (plugins_dict.workflows_dict[node.kind] ? plugins_dict.workflows_dict[node.kind].title : '<ERROR>')
              )
            }
            { listTextElement('Author', node._user.length > 0 ? node._user[0].username : 'Unknown') }
            { listTextElement('Created', utcTimeToLocal(node.insertion_date)) }
            { listTextElement('Updated', utcTimeToLocal(node.update_date)) }
        </div>
    }
    </PluginsConsumer>
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
