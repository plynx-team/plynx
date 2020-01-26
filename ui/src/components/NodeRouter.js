import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom';
import Editor from './Editor';
import NodeList from './NodeList/nodeList';
import RunList from './NodeList/runList';
import NotFound from './NotFound';

export default class NodeRouter extends Component {
  render() {
    return (
      <div className="Router NodeRouter">
        <Switch>
          <Route exact path="/nodes" component={NodeList}/>
          <Route exact path="/runs" render={(props) => <RunList {...props} showControlls={true} />}/>
          <Route path="/nodes/:node_id" render={(props) => <Editor {...props} collection="nodes" />} />
          <Route path="/runs/:node_id" render={(props) => <Editor {...props} collection="runs" />} />
          <Route path="*" component={NotFound} />
        </Switch>
      </div>
    );
  }
}
