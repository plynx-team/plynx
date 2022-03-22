import React, { Component } from 'react';
import { Route, Switch, withRouter } from 'react-router-dom';
import PropTypes from 'prop-types';
import Header from './components/Header';
import LogIn from './components/LogIn';
import LogInRedirect from './components/LogInRedirect';
import Dashboard from './components/Dashboard';
import ErrorPage from './components/ErrorPage';
import CacheBuster from './CacheBuster';
import { UserMenuContextProvider } from './contexts';
import { COLLECTIONS, VIRTUAL_COLLECTIONS, SPECIAL_USERS } from './constants';

import Editor from './components/Editor';
import UserView from './components/UserView';
import OperationList from './components/NodeList/operationList';
import WorkflowList from './components/NodeList/workflowList';
import RunList from './components/NodeList/runList';


import './App.css';

class App extends Component {
  constructor(props) {
    super(props);
    this.reloadOnChangePath = true;
  }

  getPathTuple(path) {
    const pathParts = path.split('/').concat(['', '']);
    return pathParts;
  }

  componentDidUpdate(prevProps) {
    /* A trick: reload the page every time when the url does not end with '$'*/
    const prevPathTuple = this.getPathTuple(prevProps.location.pathname);
    const pathTuple = this.getPathTuple(this.props.location.pathname);
    if (this.props.location !== prevProps.location) {
      if (this.props.location.pathname.endsWith("$")) {
        this.reloadOnChangePath = false;
        this.props.history.replace(this.props.location.pathname.replace(/\$+$/, ''));
      } else if (this.reloadOnChangePath &&
                 prevPathTuple[1] === pathTuple[1] &&
                 prevPathTuple[2] !== pathTuple[2] &&
                 prevPathTuple[2] !== '' &&
                 pathTuple[2] !== '' &&
                 prevPathTuple[2] !== 'new') {
        window.location.reload();
      } else if (this.reloadOnChangePath &&
                prevPathTuple[1] !== pathTuple[1] &&
                prevPathTuple[2] !== pathTuple[2]) {
        // Case /templates/abc -> /runs/abc
        window.location.reload();
      } else {
        this.reloadOnChangePath = true;
      }
    }
  }

  render() {
    return (
      <CacheBuster>
        {({ loading, isLatestVersion, refreshCacheAndReload }) => {
          if (loading) return null;
          if (!loading && !isLatestVersion) {
            // You can decide how and when you want to force reload
            refreshCacheAndReload();
          }

          return (
            <div className="App">
              <UserMenuContextProvider>
                <Header />
                <div className="Content">
                  <Switch>
                    <Route exact path="/" render={(props) => <LogInRedirect {...props} specialUser={SPECIAL_USERS.DEFAULT} maxTry={6} />}/>
                    <Route exact path="/demo" render={(props) => <LogInRedirect {...props} specialUser={SPECIAL_USERS.DEMO} maxTry={3} />}/>
                    <Route exact path="/dashboard" component={Dashboard} />
                    <Route exact path="/login" component={LogIn} />

                    <Route exact path={`/${VIRTUAL_COLLECTIONS.OPERATIONS}`} component={OperationList}/>
                    <Route exact path={`/${VIRTUAL_COLLECTIONS.WORKFLOWS}`} component={WorkflowList}/>
                    <Route exact path={`/${VIRTUAL_COLLECTIONS.RUNS}`} render={(props) => <RunList {...props} showControlls />}/>
                    <Route exact path={`/${COLLECTIONS.USERS}`} render={(props) => <RunList {...props} showControlls />}/>

                    <Route path={`/${COLLECTIONS.TEMPLATES}/:node_id`} render={(props) => <Editor {...props} collection={COLLECTIONS.TEMPLATES} />} />
                    <Route path={`/${COLLECTIONS.RUNS}/:node_id`} render={(props) => <Editor {...props} collection={COLLECTIONS.RUNS} />} />
                    <Route path={`/${COLLECTIONS.USERS}/:username`} render={(props) => <UserView {...props} />} />

                    <Route path="/permission_denied" render={(props) => <ErrorPage {...props} errorCode={403} />} />
                    <Route path="*" render={(props) => <ErrorPage {...props} errorCode={404} />} />
                  </Switch>
                </div>
              </UserMenuContextProvider>
            </div>
          );
        }}
      </CacheBuster>
    );
  }
}

App.propTypes = {
  location: PropTypes.object,
  history: PropTypes.object,
};

export default withRouter(App);
