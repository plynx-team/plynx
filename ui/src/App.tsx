import React, { Component } from 'react';
import { Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import Header from './components/Header';
import LogIn from './components/LogIn';
import LogInRedirect from './components/LogInRedirect';
import Dashboard from './components/Dashboard';
import ErrorPage from './components/ErrorPage';
import CacheBuster from './components/Common/CacheBuster';
import { UserMenuContextProvider } from './contexts';
import { COLLECTIONS, VIRTUAL_COLLECTIONS, SPECIAL_USERS } from './constants';
import { withRouter, RouterHistory, RouterLocation } from './router';

import Editor from './components/Editor';
import UserView from './components/UserView';
import OperationList from './components/NodeList/operationList';
import WorkflowList from './components/NodeList/workflowList';
import RunList from './components/NodeList/runList';
import LoadingScreen from './components/LoadingScreen';
import theme from './theme';
import packageInfo from '../package.json';

import './App.css';

const RoutedLogInRedirect = withRouter(LogInRedirect);
const RoutedDashboard = withRouter(Dashboard);
const RoutedLogIn = withRouter(LogIn);
const RoutedOperationList = withRouter(OperationList);
const RoutedWorkflowList = withRouter(WorkflowList);
const RoutedRunList = withRouter(RunList);
const RoutedEditor = withRouter(Editor);
const RoutedUserView = withRouter(UserView);
const RoutedErrorPage = withRouter(ErrorPage);

export interface AppProps {
  location?: RouterLocation;
  history?: RouterHistory;
}

class App extends Component<AppProps> {
  reloadOnChangePath: boolean;

  constructor(props: AppProps) {
    super(props);
    this.reloadOnChangePath = true;
  }

  getPathTuple(path: string): string[] {
    const pathParts = path.split('/').concat(['', '']);
    return pathParts;
  }

  componentDidUpdate(prevProps: AppProps) {
    /* A trick: reload the page every time when the url does not end with '$' */
    if (!this.props.location || !prevProps.location) {
      return;
    }
    const prevPathTuple = this.getPathTuple(prevProps.location.pathname);
    const pathTuple = this.getPathTuple(this.props.location.pathname);
    if (this.props.location !== prevProps.location) {
      if (this.props.location.pathname.endsWith('$')) {
        this.reloadOnChangePath = false;
        this.props.history?.replace(this.props.location.pathname.replace(/\$+$/, ''));
      } else if (
        this.reloadOnChangePath &&
        prevPathTuple[1] === pathTuple[1] &&
        prevPathTuple[2] !== pathTuple[2] &&
        prevPathTuple[2] !== '' &&
        pathTuple[2] !== '' &&
        prevPathTuple[2] !== 'new'
      ) {
        window.location.reload();
      } else if (
        this.reloadOnChangePath &&
        prevPathTuple[1] !== pathTuple[1] &&
        prevPathTuple[2] !== pathTuple[2]
      ) {
        // Case /templates/abc -> /runs/abc
        window.location.reload();
      } else {
        this.reloadOnChangePath = true;
      }
    }
  }

  render() {
    const isProduction = process.env.NODE_ENV === 'production';

    console.log(`VERSION ${packageInfo.version}:${process.env.NODE_ENV}`);
    return (
      <CacheBuster
        currentVersion={packageInfo.version}
        isEnabled={isProduction}
        isVerboseMode={false}
        loadingComponent={<LoadingScreen />}
        metaFileDirectory="."
      >
        <div className="App">
          <ThemeProvider theme={theme}>
            <UserMenuContextProvider>
              <Header />
              <div className="Content">
                <Routes>
                  <Route path="/" element={<RoutedLogInRedirect specialUser={SPECIAL_USERS.REDIRECT} maxTry={6} />} />
                  <Route path="/default" element={<RoutedLogInRedirect specialUser={SPECIAL_USERS.DEFAULT} maxTry={6} />} />
                  <Route path="/demo" element={<RoutedLogInRedirect specialUser={SPECIAL_USERS.DEMO} maxTry={3} />} />
                  <Route path="/dashboard" element={<RoutedDashboard />} />
                  <Route path="/login" element={<RoutedLogIn />} />

                  <Route path={`/${VIRTUAL_COLLECTIONS.OPERATIONS}`} element={<RoutedOperationList />} />
                  <Route path={`/${VIRTUAL_COLLECTIONS.WORKFLOWS}`} element={<RoutedWorkflowList />} />
                  <Route path={`/${VIRTUAL_COLLECTIONS.RUNS}`} element={<RoutedRunList showControlls />} />
                  <Route path={`/${COLLECTIONS.USERS}`} element={<RoutedRunList showControlls />} />

                  <Route path={`/${COLLECTIONS.TEMPLATES}/:node_id`} element={<RoutedEditor collection={COLLECTIONS.TEMPLATES} />} />
                  <Route path={`/${COLLECTIONS.RUNS}/:node_id`} element={<RoutedEditor collection={COLLECTIONS.RUNS} />} />
                  <Route path={`/${COLLECTIONS.USERS}/:username`} element={<RoutedUserView />} />

                  <Route path="/permission_denied" element={<RoutedErrorPage errorCode={403} />} />
                  <Route path="*" element={<RoutedErrorPage errorCode={404} />} />
                </Routes>
              </div>
            </UserMenuContextProvider>
          </ThemeProvider>
        </div>
      </CacheBuster>
    );
  }
}

export default withRouter(App);
