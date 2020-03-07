import React, { Component } from 'react';
import PropTypes from 'prop-types';
import cookie from 'react-cookies';

import './style.css';


export default class UserButton extends Component {
  constructor(props) {
    super(props);
    const refreshTokenExists = !!cookie.load('refresh_token');
    const username = cookie.load('username');
    this.state = {
      username: username,
      refreshTokenExists: refreshTokenExists,
    };
  }

  handleLogOut() {
    console.log("Log out");
    cookie.remove('username');
    cookie.remove('access_token');
    cookie.remove('refresh_token');
    window.location = "/login";
  }

  handleLogIn() {
    console.log("Log in");
    window.location = "/login";
  }

  render() {
    return (
      <div className="UserButton">
        {this.state.refreshTokenExists &&
          <div className="inner-user-button">
            <div className="username">
              {this.state.username}
            </div>
            -
            <div className="action" onClick={() => this.handleLogOut()}>
              LogOut
            </div>
          </div>
        }
        {!this.state.refreshTokenExists &&
          <div className="inner-user-button">
            <div className="action" onClick={() => this.handleLogIn()}>
              LogIn
            </div>
          </div>
        }
      </div>
    );
  }
}

UserButton.propTypes = {
  onAPIDialogClick: PropTypes.func,
};
