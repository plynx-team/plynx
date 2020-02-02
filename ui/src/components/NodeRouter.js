import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom';
import Editor from './Editor';
import NodeList from './NodeList/nodeList';
import RunList from './NodeList/runList';
import NotFound from './NotFound';
import { COLLECTIONS } from '../constants';


export default class NodeRouter extends Component {
  render() {
    return (
      <div className="Router NodeRouter">
        <Switch>
          <Route exact path={`/${COLLECTIONS.TEMPLATES}`} component={NodeList}/>
          <Route exact path={`/${COLLECTIONS.RUNS}`} render={(props) => <RunList {...props} showControlls={true} />}/>
          <Route path={`/${COLLECTIONS.TEMPLATES}/:node_id`} render={(props) => <Editor {...props} collection={COLLECTIONS.TEMPLATES} />} />
          <Route path={`/${COLLECTIONS.RUNS}/:node_id`} render={(props) => <Editor {...props} collection={COLLECTIONS.RUNS} />} />
          <Route path="*" component={NotFound} />
        </Switch>
      </div>
    );
  }
}
