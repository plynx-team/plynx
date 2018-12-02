import React, { Component } from 'react';
import { Link } from 'react-router-dom'
import Navigation from './navigation.js'
import UserButton from './UserButton.js'

import './style.css'

class Header extends Component {
  render() {
    return (
      <div className="Header">
        <Link to='/' className="logo"><img src='/logo.png' className='icon' /></Link>
        <Navigation />
        <UserButton />
      </div>
    );
  }
}

export default Header;
