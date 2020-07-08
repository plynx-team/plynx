import React, { Component } from 'react';
import { Route, Switch, withRouter } from 'react-router-dom';
import cookie from 'react-cookies';
import PropTypes from 'prop-types';
import Header from './components/Header';
import Settings from './components/Settings';
import LogIn from './components/LogIn';
import LogInRedirect from './components/LogInRedirect';
import Dashboard from './components/Dashboard';
import NodeRouter from './components/NodeRouter';
import NotFound from './components/NotFound';
import CacheBuster from './CacheBuster';
import { COLLECTIONS, VIRTUAL_COLLECTIONS, SPECIAL_USERS } from './constants';

import './App.css';

class App extends Component {
  constructor(props) {
    super(props);
    this.reloadOnChangePath = true;

    if (cookie.load('refresh_token') !== undefined) {
      var setting_dict = this.settingsFromCookie();
    } else {
      setting_dict = {
        'Node Display': 'Type and title',
        'Docs': true,
        'Github': true
      }
    }

    this.state = {
      options: {
        'Node Display': {
            type: 'list',
            choice: setting_dict['Node Display'],
            values: ['Type and title', 'Title and description'],
        },
        'Github' : {
            type: 'boolean',
            choice: setting_dict['Github'],
        },
        'Docs' :{
            type: 'boolean',
            choice: setting_dict['Docs'],
        },
      },
    };

    this.headerRef = React.createRef();

    this.settingChanged.bind(this);
  }

  getPathTuple(path) {
    const pathParts = path.split('/').concat(['', '']);
    return pathParts;
  }

  componentDidUpdate(prevProps) {
    /* A trick: reload the page every time when the url does not end with '$'*/
    const prevPathTuple = this.getPathTuple(prevProps.location.pathname);
    const pathTuple = this.getPathTuple(this.props.location.pathname);
    console.log(prevProps, pathTuple, 'bababich');
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

  settingChanged(options, headerRef) {
    headerRef.current.navigationRef.current.handleNavChange(options['Github'], options['Docs']);
  }

  settingsFromCookie() {
    const settings = cookie.load('settings');
    const split_settings = settings.split('-');
    var settingls = [];
    var valuedict = {};
    for (var i in split_settings) {
        settingls.push(
            split_settings[i].split('_')
        );
    }
    for (var j in settingls) {
        if (settingls[j][1] === 'true') {
            valuedict[settingls[j][0]] = true;
        } else if (settingls[j][1] === 'false') {
            valuedict[settingls[j][0]] = false;
        } else {
            valuedict[settingls[j][0]] = settingls[j][1];
        }
    }
    return valuedict
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
              <Header
                Docs={this.state.options.Docs.choice}
                Github={this.state.options.Github.choice}
                ref={this.headerRef}
              />
              <div className="Content">
                <Switch>
                  <Route exact path="/" render={(props) => <LogInRedirect {...props} specialUser={SPECIAL_USERS.DEFAULT} maxTry={6} />}/>
                  <Route exact path="/demo" render={(props) => <LogInRedirect {...props} specialUser={SPECIAL_USERS.DEMO} maxTry={3} />}/>
                  <Route exact path="/dashboard" component={Dashboard} />
                  <Route path={`/${VIRTUAL_COLLECTIONS.OPERATIONS}`} component={NodeRouter}/>
                  <Route path={`/${VIRTUAL_COLLECTIONS.WORKFLOWS}`} component={NodeRouter}/>
                  <Route path={`/${COLLECTIONS.GROUPS}`} component={NodeRouter}/>
                  <Route 
                    path={`/${COLLECTIONS.TEMPLATES}`}
                    render={
                      (props) => <NodeRouter
                        {...props}
                        nodeDis={this.state.options['Node Display']['choice']}
                      />
                    }
                    />
                  <Route path={`/${COLLECTIONS.RUNS}`} component={NodeRouter}/>
                  <Route exact path="/login" component={LogIn} />
                  <Route
                   exact
                   path="/settings"
                   render={
                    (props) => <Settings
                      {...props}
                      options={this.state.options}
                      saveFunc={this.settingChanged}
                      headerRef={this.headerRef}
                    />
                   }
                  />
                  <Route path="*" component={NotFound} />
                </Switch>
              </div>
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
