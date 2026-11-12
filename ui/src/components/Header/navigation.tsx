import React, { Component } from 'react';
import { NavLink } from 'react-router-dom';
import { separator } from './common';
import cookie from '../../cookie';
import { VIRTUAL_COLLECTIONS } from '../../constants';
import { UserMenuContext } from '../../contexts';

import './style.css';

export interface NavigationProps {
  showMenu?: boolean;
}

interface NavigationState {
  refreshTokenExists: boolean;
}

class Navigation extends Component<NavigationProps, NavigationState> {
  static contextType = UserMenuContext;

  constructor(props: Record<string, never>) {
    super(props);
    this.state = {
      refreshTokenExists: Boolean(cookie.load('refresh_token')),
    };
  }

  render() {
    return (
      <div className="Navigation">
        <div className="NavigationItems">
          {separator()}
          {this.state.refreshTokenExists && (
            <NavLink to="/dashboard" className="Item">
              Dashboard
            </NavLink>
          )}
          {this.state.refreshTokenExists && (
            <NavLink to={`/${VIRTUAL_COLLECTIONS.OPERATIONS}`} className="Item">
              Operations
            </NavLink>
          )}
          {this.state.refreshTokenExists && (
            <NavLink to={`/${VIRTUAL_COLLECTIONS.WORKFLOWS}`} className="Item">
              Workflows
            </NavLink>
          )}
          {this.state.refreshTokenExists && (
            <NavLink to={`/${VIRTUAL_COLLECTIONS.RUNS}`} className="Item">
              Runs
            </NavLink>
          )}
          {separator()}
          <a href="https://plynx.readthedocs.io/en/latest/overview.html" className="Item">
            Docs
          </a>
          {separator()}
          <a href="https://github.com/plynx-team/plynx" className="Item">
            Github
          </a>
          {separator()}
        </div>
      </div>
    );
  }
}

export default Navigation;
