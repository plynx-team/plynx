import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom';
import Editor from './Editor';
// import Group from './Group';
import OperationList from './NodeList/operationList';
import WorkflowList from './NodeList/workflowList';
import RunList from './NodeList/runList';
// import GroupList from './NodeList/groupList';
import NotFound from './NotFound';
import { COLLECTIONS, VIRTUAL_COLLECTIONS } from '../constants';


export default class NodeRouter extends Component {
  constructor(props) {
    super(props);

    if (window.location.pathname.split('/')[1] === 'templates') {
      this.state = { nodeDis: props.nodeDis };
    } else {
      this.state = {};
    }
  }

  render() {
    return (
      <div className="Router NodeRouter">
        <Switch>
          <Route exact path={`/${VIRTUAL_COLLECTIONS.OPERATIONS}`} component={OperationList}/>
          <Route exact path={`/${VIRTUAL_COLLECTIONS.WORKFLOWS}`} component={WorkflowList}/>
          <Route exact path={`/${VIRTUAL_COLLECTIONS.RUNS}`} render={(props) => <RunList {...props} showControlls />}/>
          {/* <Route exact path={`/${VIRTUAL_COLLECTIONS.GROUPS}`} render={(props) => <GroupList {...props} showControlls />}/>*/}
          <Route path={`/${COLLECTIONS.TEMPLATES}/:node_id`} render={(props) => <Editor {...props} collection={COLLECTIONS.TEMPLATES} nodeDis={this.state.nodeDis} />} />
          <Route path={`/${COLLECTIONS.RUNS}/:node_id`} render={(props) => <Editor {...props} collection={COLLECTIONS.RUNS} />} />
          {/* <Route path={`/${COLLECTIONS.GROUPS}/:group_id`} render={(props) => <Group {...props} collection={COLLECTIONS.GROUPS} />} />*/}
          <Route path="*" component={NotFound} />
        </Switch>
      </div>
    );
  }
}
