import React, { Component } from 'react';
import PropTypes from 'prop-types';
import cookie from 'react-cookies';
import { UserMenuContext } from '../../contexts';
import { User } from 'react-feather';

import './style.css';


export default class UserButton extends Component {
  constructor(props) {
    super(props);
    const refreshTokenExists = !!cookie.load('refresh_token');
    const user = cookie.load('user');
    this.state = {
      user: user,
      refreshTokenExists: refreshTokenExists,
    };
  }

  handleLogIn() {
    console.log("Log in");
    window.location = "/login";
  }

  render() {
    let username = '';
    if (this.state.user) {
      if (this.state.user.settings && this.state.user.settings.display_name) {
        username = this.state.user.settings.display_name;
      } else {
        username = this.state.user.username;
      }
    }

    return (
      <div className="UserButton">
        {this.state.refreshTokenExists &&
          <UserMenuContext.Consumer>{(context) => {
            return (
                <div className="inner-user-button">
                  <a className="user-menu" href={`/users/${this.state.user.username}`} onClick={(e) => {
                    context.toggleModal();
                    e.preventDefault();
                  }}>
                    <User/>
                    <div className="username">
                      {username}
                    </div>
                  </a>
                </div>
            );
          }}</UserMenuContext.Consumer>
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
