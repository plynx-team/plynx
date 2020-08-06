import React, { createContext, Component } from "react";
import PropTypes from 'prop-types';


const PluginsContext = React.createContext({});

export const PluginsProvider = PluginsContext.Provider;
export const PluginsConsumer = PluginsContext.Consumer;


export const UserMenuContext = createContext();

export class UserMenuContextProvider extends Component {
  static propTypes = {
    children: PropTypes.oneOfType([
      PropTypes.array.isRequired,
      PropTypes.object.isRequired,
    ]),
  }

  state = {
    showModal: false,
  }

  toggleModal = () => {
    this.setState({ showModal: !this.state.showModal });
  }

  hideModal = () => {
    this.setState({ showModal: false });
  }

  render() {
    return (
            <UserMenuContext.Provider value={{...this.state, hideModal: this.hideModal, toggleModal: this.toggleModal}}>
                {this.props.children}
            </UserMenuContext.Provider>
    );
  }
}
