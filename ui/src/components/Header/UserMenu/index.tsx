import React, { Component, createRef } from 'react';
import cookie from '../../../cookie';
import { UserMenuContext, UserMenuContextType } from '../../../contexts';
import { User } from '../../../types';

import './style.css';

interface SettingsState {
  user: User | null;
}

export class Settings extends Component<Record<string, never>, SettingsState> {
  static contextType = UserMenuContext;
  declare context: UserMenuContextType;
  wrapperRef = createRef<HTMLDivElement>();

  constructor(props: Record<string, never>) {
    super(props);
    this.state = {
      user: cookie.load('user') || null,
    };
  }

  componentDidMount() {
    document.addEventListener('mousedown', this.handleDocumentMouseDown);
  }

  componentWillUnmount() {
    document.removeEventListener('mousedown', this.handleDocumentMouseDown);
  }

  handleDocumentMouseDown = (event: MouseEvent) => {
    if (!this.context || !this.context.showModal) {
      return;
    }
    const target = event.target as HTMLElement | null;
    if (this.wrapperRef.current && target && this.wrapperRef.current.contains(target)) {
      return;
    }
    if (target && target.closest && target.closest('.UserButton')) {
      return;
    }
    this.context.hideModal();
  };

  handleSignOut() {
    cookie.remove('user');
    cookie.remove('access_token');
    cookie.remove('refresh_token');
    window.location.href = '/login';
  }

  render() {
    const { user } = this.state;
    if (!user) {
      return null;
    }

    return (
      <UserMenuContext.Consumer>
        {(context: UserMenuContextType) => (
          <div className="user-menu-wrapper" ref={this.wrapperRef}>
            {context.showModal && (
              <div className="user-menu-grid">
                <div className="menu-item menu-item-name">
                  @{user.settings?.display_name || user.username}
                </div>
                <a className="menu-item menu-item-clickable" href={`/users/${user.username}`}>
                  Settings
                </a>
                <div className="menu-item menu-item-clickable" onClick={() => this.handleSignOut()}>
                  Sign Out
                </div>
              </div>
            )}
          </div>
        )}
      </UserMenuContext.Consumer>
    );
  }
}

export default Settings;
