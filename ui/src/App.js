import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom'
import { withRouter } from 'react-router-dom';
import cookie from 'react-cookies'

import Header from './components/header';
import About from './components/About';
import LogIn from './components/LogIn';
import Welcome from './components/Welcome';
import Dashboard from './components/dashboard';
import NodeRouter from './components/NodeRouter.js';
import FileRouter from './components/FileRouter.js';
import GraphRouter from './components/GraphRouter.js';
import NotFound from './components/NotFound';
import FeedbackButton from './components/FeedbackButton'
import APIDialog from './components/Dialogs/APIDialog'

import './App.css';

class App extends Component {

  constructor(props) {
    super(props);
    this.reloadOnChangePath = true;
    this.state = {};
  }

  getPathTuple(path) {
    var pathParts = path.split('/').concat(['', '']);
    return pathParts;
  }

  componentDidUpdate(prevProps) {
    /* A trick: reload the page every time when the url does not end with '$'*/
    var prevPathTuple = this.getPathTuple(prevProps.location.pathname);
    var pathTuple = this.getPathTuple(this.props.location.pathname);
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
      } else {
        this.reloadOnChangePath = true;
      }
    }
  }

  handleAPIDialogClick() {
    this.setState({showApiDialog: true});
  }

  handleAPIDialogClose() {
    this.setState({showApiDialog: false});
  }

  render() {
    return (
      <div className="App">
        <Header onAPIDialogClick={() => this.handleAPIDialogClick()}/>
        {cookie.load('username') &&
          <FeedbackButton/>
        }
        <div className="Content">
          {this.state.showApiDialog && <APIDialog onClose={() => this.handleAPIDialogClose()}/>}
          <Switch>
            <Route exact path="/" component={Welcome} />
            <Route exact path="/welcome" component={Welcome} />
            <Route exact path="/dashboard" component={Dashboard} />
            <Route path="/nodes" component={NodeRouter}/>
            <Route path="/files" component={FileRouter}/>
            <Route path="/graphs" component={GraphRouter}/>
            <Route exact path="/about" component={About} />
            <Route exact path="/login" component={LogIn} />
            <Route path="*" component={NotFound} />
          </Switch>
        </div>
      </div>
    );
  }
}

export default withRouter(App);
