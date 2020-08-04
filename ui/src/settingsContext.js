import React, { createContext, Component } from "react";

export const SettingsContext = createContext();

export class SettingsContextProvider extends Component {
  state = {
    options: {
      'Node Display': {
        'type': 'list',
        'choice': 'Type and title',
        'values': ['Type and title', 'Title and description'],
      },
      'Github': {
        'type': 'boolean',
        'choice': true,
      },
      'Docs': {
        'type': 'boolean',
        'choice': true,
      }
    },
    showModal: false,
  }

  toggleModal = () => {
    this.setState({ showModal: !this.state.showModal });
  }

  hideModal = () => {
    this.setState({ showModal: false });
  }

  setSettings = (dict) => {
    this.setState({ options: dict });
  }

  render() {
    return (
            <SettingsContext.Provider value={{...this.state,
              hideModal: this.hideModal,
              toggleModal: this.toggleModal,
              setSettings: this.setSettings
            }}>
                {this.props.children}
            </SettingsContext.Provider>
    );
  }
}
