import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import BaseList from '../BaseList';
import { listTextElement } from '../Common/listElements';
import '../Common/ListPage.css';
import '../controls.css';
import './items.css'


export function renderItem(item) {
  return (
      <a
        className='list-item graph-list-item'
        href={'/graphs/' + item._id}
        key={item._id}
      >
        <div className='TitleDescription'>
          <div className='Title'>
            {item.title}
          </div>
          <div className='Description'>
            &ldquo;{item.description}&rdquo;
          </div>
        </div>

        { listTextElement('Status ' + item.graph_running_status, item.graph_running_status) }
        { listTextElement('Id', item._id) }
        { listTextElement('Author', item._user[0].username) }
        { listTextElement('Created', item.insertion_date) }
        { listTextElement('Updated', item.update_date) }
      </a>
    );
};

export const LIST_HEADER = [
   {title: "Header", tag: ""},
   {title: "Status", tag: "Status"},
   {title: "Graph Id", tag: "Id"},
   {title: "Author", tag: "Author"},
   {title: "Created", tag: "Created"},
   {title: "Updated", tag: "Updated"},
];

export default class ListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Graphs - PLynx";
  }

  render() {
    return (
        <BaseList
            menu={() => <a className="menu-button" href="/graphs/new">{"Create new Graph"}</a>}
            tag="graph-list-item"
            endpoint={PLynxApi.endpoints.search_graphs}
            header={LIST_HEADER}
            renderItem={renderItem}
        >
        </BaseList>
    );
  }
}
