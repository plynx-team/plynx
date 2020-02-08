import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom';
import Editor from './Editor';
import OperationList from './nodeList/operationList';
import WorkflowList from './nodeList/workflowList';
import RunList from './nodeList/runList';
import NotFound from './NotFound';
import { COLLECTIONS, VIRTUAL_COLLECTIONS } from '../constants';


export default class NodeRouter extends Component {
  render() {
    return (
      <div className="Router NodeRouter">
        <Switch>
          <Route exact path={`/${VIRTUAL_COLLECTIONS.OPERATIONS}`} component={OperationList}/>
          <Route exact path={`/${VIRTUAL_COLLECTIONS.WORKFLOWS}`} component={WorkflowList}/>
          <Route exact path={`/${VIRTUAL_COLLECTIONS.RUNS}`} render={(props) => <RunList {...props} showControlls={true} />}/>
          <Route path={`/${COLLECTIONS.TEMPLATES}/:node_id`} render={(props) => <Editor {...props} collection={COLLECTIONS.TEMPLATES} />} />
          <Route path={`/${COLLECTIONS.RUNS}/:node_id`} render={(props) => <Editor {...props} collection={COLLECTIONS.RUNS} />} />
          <Route path="*" component={NotFound} />
        </Switch>
      </div>
    );
  }
}
