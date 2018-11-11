// src/components/About/index.js
import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom'
import Node from './Node';
import NodeList from './NodeList';
import NotFound from './NotFound';

export default class NodeRouter extends Component {
  render() {
    return (
      <div className="NodeRouter">
        <Switch>
          <Route exact path="/nodes" component={NodeList}/>
          <Route path="/nodes/:node_id" component={Node} />
          <Route path="*" component={NotFound} />
        </Switch>
      </div>
    );
  }
}
