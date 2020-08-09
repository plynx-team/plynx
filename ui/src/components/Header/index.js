import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Navigation from './navigation';
import UserButton from './UserButton';
import UserMenu from './UserMenu';

import './style.css';

export default class Header extends Component {
  constructor(props) {
    super(props);

    this.state = {
      width: 0,
      height: 0,
      showMenu: false,
    };

    this.navigationRef = React.createRef();

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
    const showMenuButton = this.state.width < 1100;
    const showMenu = !showMenuButton || this.state.showMenu;

    return (
      <div className="Header" onMouseUp={() => this.onMouseUp()}>
        <UserMenu/>
        <a href='https://plynx.com' className="logo"><img src='/logo.png' className='icon' alt='PLynx'/></a>
        <div className={'menu-sl' + (showMenu ? "-show" : "-hide")} id='menu-sl'>
          <Navigation
            showMenu={showMenu}
            ref={this.navigationRef}
          />
        </div>
        {
          showMenuButton &&
          <div className="menu-button-sl" onMouseUp={(e) => this.onMenuClick(e)}>
            <img src="/icons/menu.svg" alt="menu" />
          </div>
        }
        <UserButton onAPIDialogClick={() => this.props.onAPIDialogClick()}/>
      </div>
    );
  }
}

Header.propTypes = {
  onAPIDialogClick: PropTypes.func,
};
