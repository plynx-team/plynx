import React, { Component, createRef, MouseEvent } from 'react';
import Navigation from './navigation';
import UserButton from './UserButton';
import UserMenu from './UserMenu';

import './style.css';

interface HeaderState {
  width: number;
  height: number;
  showMenu: boolean;
}

export default class Header extends Component<Record<string, never>, HeaderState> {
  navigationRef = createRef<any>();

  constructor(props: Record<string, never>) {
    super(props);

    this.state = {
      width: typeof window !== 'undefined' ? window.innerWidth : 0,
      height: typeof window !== 'undefined' ? window.innerHeight : 0,
      showMenu: false,
    };

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

  onMenuClick(e: MouseEvent<HTMLDivElement>) {
    this.setState({ showMenu: !this.state.showMenu });
    e.stopPropagation();
  }

  onMouseUp() {
    this.setState({ showMenu: false });
  }

  render() {
    const showMenuButton = this.state.width < 1100;
    const showMenu = !showMenuButton || this.state.showMenu;

    return (
      <div className="Header" onMouseUp={() => this.onMouseUp()}>
        <UserMenu />
        <a href="https://plynx.com" className="logo">
          <img src="/logo.png" className="icon" alt="PLynx" />
        </a>
        <div className={`menu-sl${showMenu ? '-show' : '-hide'}`} id="menu-sl">
          <Navigation ref={this.navigationRef} />
        </div>
        {showMenuButton && (
          <div className="menu-button-sl" onMouseUp={(e) => this.onMenuClick(e)}>
            <img src="/icons/menu.svg" alt="menu" />
          </div>
        )}
        <UserButton />
      </div>
    );
  }
}
