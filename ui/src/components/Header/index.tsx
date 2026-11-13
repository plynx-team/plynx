import React, { Component, createRef, MouseEvent } from 'react';
import Navigation from './navigation';
import UserButton from './UserButton';
import UserMenu from './UserMenu';

import './style.css';

const MOBILE_BREAKPOINT = 768;

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
      width: typeof window !== 'undefined' ? window.innerWidth : 1200,
      height: typeof window !== 'undefined' ? window.innerHeight : 800,
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
    const width = window.innerWidth;
    this.setState((prevState) => ({
      width,
      height: window.innerHeight,
      showMenu: width >= MOBILE_BREAKPOINT ? false : prevState.showMenu,
    }));
  }

  onMenuClick(e: MouseEvent<HTMLDivElement>) {
    e.stopPropagation();
    this.setState((prevState) => ({ showMenu: !prevState.showMenu }));
  }

  onMouseUp() {
    if (this.state.showMenu) {
      this.setState({ showMenu: false });
    }
  }

  render() {
    const showMenuButton = this.state.width < MOBILE_BREAKPOINT;
    const showMenu = !showMenuButton || this.state.showMenu;

    return (
      <div className="Header" onMouseUp={() => this.onMouseUp()}>
        <UserMenu />
        <div className="header-left">
          {showMenuButton && (
            <div
              className="menu-button-sl"
              onMouseUp={(e) => this.onMenuClick(e)}
              role="button"
              tabIndex={0}
              aria-label="Toggle navigation menu"
            >
              <img src="/icons/menu.svg" alt="menu" />
            </div>
          )}
          <a href="https://plynx.com" className="logo">
            <img src="/logo.png" className="icon" alt="PLynx" />
          </a>
        </div>
        <div className={`menu-sl${showMenu ? '-show' : '-hide'}`} id="menu-sl">
          <Navigation ref={this.navigationRef} />
        </div>
        <UserButton />
      </div>
    );
  }
}
