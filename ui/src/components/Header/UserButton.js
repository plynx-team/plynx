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
    console.log("Sign Up / Log in");
    window.location = "/login";
  }

  render() {
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
                    { this.state.user.settings.picture &&
                      <img src={this.state.user.settings.picture} className="user-icon" alt="Google profile pic" referrerPolicy="no-referrer"/>
                    }
                    { !this.state.user.settings.picture && <User className="user-icon"/> }
                  </a>
                </div>
            );
          }}</UserMenuContext.Consumer>
        }
        {!this.state.refreshTokenExists &&
          <div className="inner-user-button">
            <div className="action" onClick={() => this.handleLogIn()}>
              Sign up / Log in
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
