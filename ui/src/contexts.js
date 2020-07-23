import React, { createContext, Component } from "react";

const PluginsContext = React.createContext({});
export const ModalContext = createContext();

export const PluginsProvider = PluginsContext.Provider;
export const PluginsConsumer = PluginsContext.Consumer;

export class ModalContextProvider extends Component {
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
            <ModalContext.Provider value={{...this.state, hideModal: this.hideModal, toggleModal:this.toggleModal}}>
                {this.props.children}
            </ModalContext.Provider>
        )
    }
}