import React, { Component } from 'react';
import cookie from 'react-cookies';
import onClickOutside from "react-onclickoutside";
import { API_ENDPOINT } from '../../configConsts';

import Inputs from './Inputs';
import { SettingsContext } from '../../settingsContext';

import './style.css';
import { PLynxApi } from '../../API';

export class Settings extends Component {
    static contextType = SettingsContext;

    constructor(props) {
        super(props);

        this.state = {
            options: props.options,
        };

        this.handleInputChange.bind(this);

        document.title = "Settings - PLynx";
    }

    
    componentDidMount() {
        PLynxApi.endpoints.pull_settings.getCustom({
            method: 'post',
            url: API_ENDPOINT + '/pull_settings',
            headers: { 'token': cookie.load('access_token') },
        }).then((response) => {
            this.context.setSettings(response.data);
        }).catch((error) => {
            console.log(error);
        });
    }

    handleInputChange = (e) => {
        var main_title;
        var dict = this.context.options;

        if (e.target.className.includes('boolean-input')) {
            main_title = e.target.className.replace('boolean-input-', '');
            dict[main_title].choice = !dict[main_title].choice;
        } else if (e.target.className.includes('list-input')) {
            main_title = e.target.className.replace('list-input-', '');
            dict[main_title].choice = e.target.value;
        }
        this.context.setSettings(dict);

        const keys = Object.keys(dict);
        var value_obj = {};
        for (var i in keys) {
            value_obj[keys[i]] = dict[keys[i]]['choice'];
        }

        PLynxApi.endpoints.user_settings.getCustom({
            method: 'post',
            url: API_ENDPOINT + '/user_settings',
            headers: {
                'values': JSON.stringify(value_obj),
                'token': cookie.load('access_token'),
            },
        })
          .then(() => {
            console.log('Settings Updated!');
           }).catch((error) => {
              console.log(error); 
           });
    }

    handleClickOutside = (e) => {
        if (e.target.className.baseVal !== 'cogPath') {
            this.context.hideModal();
        }
    }

    render() {
      return (
        <SettingsContext.Consumer>{(context) => {
            return (
                <div className='setting-wrapper'>
                    {context.showModal &&
                        <div className='option-grid'>
                            <div className='header'>Settings</div>
                            <Inputs 
                                options={this.context.options}
                                input_change={this.handleInputChange}
                            />
                        </div>
                    }
                </div>
            )    
        }}</SettingsContext.Consumer>
      );
    }
  }

  export default onClickOutside(Settings);