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
        <div className='login-redirect'>
          <div className="login-redirect-logo">
              <div className="error-text">
                404: not found
              </div>
          </div>
        </div>
    );
  }
}
