import React, { Component } from 'react';
import { NavLink } from 'react-router-dom';
import { separator } from './common';
import cookie from 'react-cookies';
import { VIRTUAL_COLLECTIONS } from '../../constants';

import './style.css';

class Navigation extends Component {
  constructor(props) {
    super(props);
    this.state = {
      refreshTokenExists: !!cookie.load('refresh_token'),
      Docs: props.Docs,
      Github: props.Github,
    };

    this.handleNavChange.bind(this);
  }

  handleNavChange(GithubVal, DocsVal) {
    this.setState({
      Docs: DocsVal,
      Github: GithubVal,
    });
  }

  render() {
    return (
      <div className="Navigation">
          <div className="NavigationItems">
            {separator()}
            {this.state.refreshTokenExists &&
              <NavLink to='/dashboard' className="Item">Dashboard</NavLink>
            }
            {this.state.refreshTokenExists &&
              <NavLink to={`/${VIRTUAL_COLLECTIONS.OPERATIONS}`} className="Item">Operations</NavLink>
            }
            {/* this.state.refreshTokenExists &&
              <NavLink to={`/${VIRTUAL_COLLECTIONS.GROUPS}`} className="Item">Groups</NavLink>*/
            }
            {this.state.refreshTokenExists &&
              <NavLink to={`/${VIRTUAL_COLLECTIONS.WORKFLOWS}`} className="Item">Workflows</NavLink>
            }
            {this.state.refreshTokenExists &&
              <NavLink to={`/${VIRTUAL_COLLECTIONS.RUNS}`} className="Item">Runs</NavLink>
            }
            {separator()}
            {this.state.Docs && 
              <a href='https://plynx.readthedocs.io/en/latest/overview.html' className="Item">Docs</a>
            }
            {separator()}
            {this.state.Github && 
              <a href='https://github.com/plynx-team/plynx' className="Item">Github</a>
            }
            {separator()}
          </div>
      </div>
    );
  }
}

export default Navigation;
