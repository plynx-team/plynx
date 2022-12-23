import React, { Component } from 'react';
import cookie from 'react-cookies';
import onClickOutside from "react-onclickoutside";

import { UserMenuContext } from '../../../contexts';

import './style.css';

export class Settings extends Component {
  static contextType = UserMenuContext;

  constructor(props) {
    super(props);

    const user = cookie.load('user');

    this.state = {
      user: user,
    };
  }

  handleClickOutside = () => {
    this.context.hideModal();
  };

  handleSignOut() {
    console.log("Log out");
    cookie.remove('user');
    cookie.remove('access_token');
    cookie.remove('refresh_token');
    window.location = "/login";
  }

  render() {
    return (
        <UserMenuContext.Consumer>{(context) => {
          return (
                <div className='user-menu-wrapper'>
                    {context.showModal &&
                        <div className='user-menu-grid'>
                            <div className="menu-item menu-item-name">
                              @{this.state.user.settings.display_name || this.state.user.username}
                            </div>
                            <a className='menu-item menu-item-clickable' href={`/users/${this.state.user.username}`}>
                              Settings
                            </a>
                            <div className='menu-item menu-item-clickable' onClick={() => this.handleSignOut()}>
                              Sign Out
                            </div>
                        </div>
                    }
                </div>
          );
        }}</UserMenuContext.Consumer>
    );
  }
  }

export default onClickOutside(Settings);
