import React, { Component } from 'react';
import cookie from 'react-cookies';
import onClickOutside from "react-onclickoutside";

import { SettingsContext } from '../../../settingsContext';

import './style.css';

export class Settings extends Component {
  static contextType = SettingsContext;

  constructor(props) {
    super(props);

    const user = cookie.load('user');

    this.state = {
      user: user,
    };
  }

  handleClickOutside = () => {
    this.context.hideModal();
  }

  handleLogOut() {
    console.log("Log out");
    cookie.remove('user');
    cookie.remove('access_token');
    cookie.remove('refresh_token');
    window.location = "/login";
  }

  render() {
    return (
        <SettingsContext.Consumer>{(context) => {
          return (
                <div className='user-menu-wrapper'>
                    {context.showModal &&
                        <div className='user-menu-grid'>
                            <a className='menu-item' href={`/users/${this.state.user.username}`}>
                              Settings
                            </a>
                            <div className='menu-item' onClick={() => this.handleLogOut()}>
                              LogOut
                            </div>
                        </div>
                    }
                </div>
          );
        }}</SettingsContext.Consumer>
    );
  }
  }

export default onClickOutside(Settings);
