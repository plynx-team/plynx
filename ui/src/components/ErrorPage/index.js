import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { AlertOctagon } from 'react-feather';

import './style.css';

export default class NotFound extends Component {
  static propTypes = {
    errorCode: PropTypes.number.isRequired,
  }

  constructor(props) {
    super(props);
    if (this.props.errorCode === 403) {
      document.title = "Permission Denied - PLynx";
      this.errorText = "403: permission denied";
    } else if (this.props.errorCode === 404) {
      document.title = "Not Found - PLynx";
      this.errorText = "404: not found";
    }
  }

  render() {
    return (
        <div className='login-redirect'>
          <div className="login-redirect-logo">
              <AlertOctagon className="error-icon" />
              <div className="error-text">
                {this.errorText}
              </div>
          </div>
        </div>
    );
  }
}
