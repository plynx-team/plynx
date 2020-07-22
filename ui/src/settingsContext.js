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
            'Docs':{
                'type': 'boolean',
                'choice': true,
            }
        }
    }

    render() {
        return (
            <SettingsContext.Provider value={{...this.state}}>
                {this.props.children}
            </SettingsContext.Provider>
        )
    }
}