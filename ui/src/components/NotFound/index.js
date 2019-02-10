// src/components/NotFound/index.js
import React, { Component } from 'react';

import './style.css';

export default class NotFound extends Component {
  constructor(props) {
    super(props);
    document.title = "404 - PLynx";
  }
  render() {
    return (
      <div className='NotFound'>
        <h1>
          404 <small>Not Found :(</small>
        </h1>
      </div>
    );
  }
}
