// src/components/About/index.js
import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom'
import FileList from './FileList';
import NotFound from './NotFound';

export default class FileRouter extends Component {
  render() {
    return (
      <div className="Router FileRouter">
        <Switch>
          <Route exact path="/files" component={FileList}/>
          <Route path="/files/:file_id" component={FileList} />
          <Route path="*" component={NotFound} />
        </Switch>
      </div>
    );
  }
}
