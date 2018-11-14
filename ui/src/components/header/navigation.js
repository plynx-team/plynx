import React, { Component } from 'react';
import { NavLink } from 'react-router-dom'
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
    console.log(...this.props);
    return (
      <div className="Navigation" onMouseUp={this.onMouseUp}>
          <div className="NavigationItems">
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
            -
            <NavLink to='https://github.com/khaxis/plynx' className="Item">Github</NavLink>
          </div>
      </div>
    );
  }
}

export default Navigation;
