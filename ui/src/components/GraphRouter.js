// src/components/About/index.js
import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom';
import Graph from './Graph';
import GraphList from './GraphList';
import NotFound from './NotFound';

export default class GraphRouter extends Component {
  render() {
    return (
      <div className="Router GraphRouter">
        <Switch>
          <Route exact path="/graphs" component={GraphList}/>
          <Route path="/graphs/:graph_id" component={Graph} />
          <Route path="*" component={NotFound} />
        </Switch>
      </div>
    );
  }
}
