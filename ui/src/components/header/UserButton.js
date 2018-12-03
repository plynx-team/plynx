import React, { Component } from 'react';
import cookie from 'react-cookies'

import './style.css'

class UserButton extends Component {
  constructor(props) {
    super(props);
    var refreshTokenExists = cookie.load('refresh_token') ? true : false;
    var username = cookie.load('username');
    this.state = {
      username: username,
      refreshTokenExists: refreshTokenExists,
    }
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

  handleAPIClick() {
  }

  render() {
    return (
      <div className="UserButton">
        {this.state.refreshTokenExists &&
          <div className="api-button">
            <a className="button logo" href='#' onClick={() => this.handleAPIClick()}>
              API
            </a>
          </div>
        }
        {this.state.refreshTokenExists &&
          <div className="inner-user-button">
            <div className="username">
              {this.state.username}
            </div>
            <div className="separator">
              -
            </div>
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

export default UserButton;
