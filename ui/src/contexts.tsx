import React, { createContext, Component, ReactNode } from 'react';
import { PluginsDict } from './types';

export const PluginsContext = createContext<PluginsDict>({
  resources_dict: {},
  executors_info: {},
});

export const PluginsProvider = PluginsContext.Provider;
export const PluginsConsumer = PluginsContext.Consumer;

export interface UserMenuContextType {
  showModal: boolean;
  toggleModal: () => void;
  hideModal: () => void;
}

export const UserMenuContext = createContext<UserMenuContextType>({
  showModal: false,
  toggleModal: () => {},
  hideModal: () => {},
});

interface UserMenuContextProviderProps {
  children?: ReactNode;
}

interface UserMenuContextProviderState {
  showModal: boolean;
}

export class UserMenuContextProvider extends Component<UserMenuContextProviderProps, UserMenuContextProviderState> {
  state: UserMenuContextProviderState = {
    showModal: false,
  };

  toggleModal = (): void => {
    this.setState({ showModal: !this.state.showModal });
  };

  hideModal = (): void => {
    this.setState({ showModal: false });
  };

  render() {
    return (
      <UserMenuContext.Provider
        value={{
          ...this.state,
          hideModal: this.hideModal,
          toggleModal: this.toggleModal,
        }}
      >
        {this.props.children}
      </UserMenuContext.Provider>
    );
  }
}
