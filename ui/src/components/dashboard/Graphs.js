import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import { LIST_HEADER, renderItem } from '../GraphList';
import BaseList from '../nodeList/baseList';
import './Graphs.css';

export default class Graphs extends Component {
  render() {
    return (
      <div className='graphs-state'>
        <div className='header'>
          Recent Graphs
        </div>

        <BaseList
            tag="graph-list-item"
            endpoint={PLynxApi.endpoints.search_graphs}
            header={LIST_HEADER}
            renderItem={renderItem}
            search="order:update_date"
        >
        </BaseList>

      </div>
    );
  }
}
