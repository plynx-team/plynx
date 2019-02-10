import React, { Component } from 'react';
import { Link } from 'react-router-dom'
import Navigation from './navigation.js'
import UserButton from './UserButton.js'

import './style.css'

class Header extends Component {

  constructor(props) {
    super(props);
    this.state = { width: 0, height: 0, showMenu: false };
    this.updateWindowDimensions = this.updateWindowDimensions.bind(this);
  }

  componentDidMount() {
    this.updateWindowDimensions();
    window.addEventListener('resize', this.updateWindowDimensions);
  }

  componentWillUnmount() {
    window.removeEventListener('resize', this.updateWindowDimensions);
  }

  updateWindowDimensions() {
    this.setState({ width: window.innerWidth, height: window.innerHeight });
  }

  onMenuClick(e) {
    this.setState({showMenu: !this.state.showMenu});
    e.stopPropagation();
  }

  onMouseUp() {
    this.setState({showMenu: false});
  }

  render() {
    var showMenuButton = this.state.width < 1100;
    var showMenu = !showMenuButton || this.state.showMenu;

    return (
      <div className="Header" onMouseUp={() => this.onMouseUp()}>
        <Link to='/' className="logo"><img src='/logo.png' className='icon' alt='PLynx'/></Link>
        <div className={'menu-sl' + (showMenu ? "-show": "-hide")} id='menu-sl'>
          <Navigation showMenu={showMenu}/>
        </div>
        {
          showMenuButton &&
          <a className="menu-button-sl" href={null} onMouseUp={(e) => this.onMenuClick(e)}>
            <img src="/icons/menu.svg" alt="menu" />
          </a>
        }
        <UserButton onAPIDialogClick={() => this.props.onAPIDialogClick()}/>
      </div>
    );
  }
}

export default Header;
