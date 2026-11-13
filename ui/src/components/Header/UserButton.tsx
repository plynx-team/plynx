import React, { Component } from 'react';
import cookie from '../../cookie';
import { UserMenuContext, UserMenuContextType } from '../../contexts';
import { FeatherIcon } from '../Common/Icon';
import { User } from '../../types';

import './style.css';

interface UserButtonState {
  user: User | null;
  refreshTokenExists: boolean;
}

export default class UserButton extends Component<Record<string, never>, UserButtonState> {
  constructor(props: Record<string, never>) {
    super(props);
    const refreshTokenExists = Boolean(cookie.load('refresh_token'));
    const user = cookie.load('user');
    this.state = {
      user: user || null,
      refreshTokenExists,
    };
  }

  handleLogIn() {
    window.location.href = '/login';
  }

  render() {
    const { user, refreshTokenExists } = this.state;

    return (
      <div className="UserButton">
        {refreshTokenExists && user && (
          <UserMenuContext.Consumer>
            {(context: UserMenuContextType) => (
              <div className="inner-user-button">
                <a
                  className="user-menu"
                  href={`/users/${user.username}`}
                  onClick={(e) => {
                    context.toggleModal();
                    e.preventDefault();
                  }}
                >
                  {user.settings?.picture ? (
                    <img
                      src={user.settings.picture}
                      className="user-icon"
                      alt="Google profile pic"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <FeatherIcon name="user" className="user-icon" />
                  )}
                </a>
              </div>
            )}
          </UserMenuContext.Consumer>
        )}
        {!refreshTokenExists && (
          <div className="inner-user-button">
            <div className="action" onClick={() => this.handleLogIn()}>
              Sign up / Log in
            </div>
          </div>
        )}
      </div>
    );
  }
}
