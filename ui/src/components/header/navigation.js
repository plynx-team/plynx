import React, { Component } from 'react';
import { NavLink } from 'react-router-dom'
import { separator } from './common'
import cookie from 'react-cookies'

import './style.css'

class Navigation extends Component {
  constructor(props) {
    super(props);
    this.state = {
      refreshTokenExists: cookie.load('refresh_token') ? true : false
    }
  }

  onMouseUp(e) {
    console.log("up");
  }

  render() {
    return (
      <div className="Navigation" onMouseUp={this.onMouseUp}>
          <div className="NavigationItems">
            {separator()}
            {this.state.refreshTokenExists &&
              <NavLink to='/dashboard' className="Item">Dashboard</NavLink>
            }
            {this.state.refreshTokenExists &&
              <NavLink to='/files' className="Item">Files</NavLink>
            }
            {this.state.refreshTokenExists &&
              <NavLink to='/nodes' className="Item">Operations</NavLink>
            }
            {this.state.refreshTokenExists &&
              <NavLink to='/graphs' className="Item">Graphs</NavLink>
            }
            <NavLink to='/about' className="Item">About</NavLink>
            {separator()}
            <a href='https://github.com/khaxis/plynx' className="Item">Github</a>
            {separator()}
          </div>
      </div>
    );
  }
}

export default Navigation;
