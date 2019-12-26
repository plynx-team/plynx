import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom';
import Editor from './Editor';
import NodeList from './NodeList';
import NotFound from './NotFound';

export default class NodeRouter extends Component {
  render() {
    return (
      <div className="Router NodeRouter">
        <Switch>
          <Route exact path="/nodes" component={NodeList}/>
          <Route path="/nodes/:node_id" component={Editor} />
          <Route path="*" component={NotFound} />
        </Switch>
      </div>
    );
  }
}
