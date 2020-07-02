import React, { Component } from 'react';
import cookie from 'react-cookies';
import { API_ENDPOINT } from '../../configConsts';

import Inputs from './Inputs';

import './style.css';
import { PLynxApi } from '../../API';

export default class Settings extends Component {
    constructor(props) {
        super(props);

        const settings = cookie.load('settings');
        const split_settings = settings.split('-');
        var settingls = [];
        var valuedict = {};
        for (var i in split_settings) {
            settingls.push(
                split_settings[i].split('_')
            );
        }
        for (var j in settingls) {
            if (settingls[j][1] === 'true') {
                valuedict[settingls[j][0]] = true;
            } else if (settingls[j][1] === 'false') {
                valuedict[settingls[j][0]] = false;
            } else {
                valuedict[settingls[j][0]] = settingls[j][1];
            }
        }        

        this.state = {
            options: {
                'Theme': {
                    type: 'list',
                    choice: valuedict['Theme'],
                    values: ['one', 'two', 'three'],
                },
                'Github' : {
                    type: 'boolean',
                    choice: valuedict['Github'],
                },
                'Docs' :{
                    type: 'boolean',
                    choice: valuedict['Docs'],
                },
            },
            changes: 'disabled',
        };

        this.handleInputChange.bind(this);
        this.handleSave.bind(this);

        document.title = "Settings - PLynx";
    }

    handleInputChange = (e) => {
        this.setState({changes: 'enabled'});
        var main_title;
        var dic = this.state.options;

        if (e.target.className.includes('boolean-input')) {
            main_title = e.target.className.replace('boolean-input-', '');
            dic[main_title].choice = !dic[main_title].choice;
        } else if (e.target.className.includes('list-input')) {
            main_title = e.target.className.replace('list-input-', '');
            dic[main_title].choice = e.target.value;
        }
        this.setState({options:dic});
    }

    handleSave = () => {
        const dict = this.state.options;
        const keys = Object.keys(dict);
        var value_obj = {};
        for (var i in keys) {
            value_obj[keys[i]] = dict[keys[i]]['choice'];
        }

        PLynxApi.endpoints.settings.getCustom({
            method: 'post',
            url: API_ENDPOINT + '/settings',
            headers: {'values': JSON.stringify(value_obj)},
        })
          .then((response) => {
              cookie.save('settings', response.data);
              this.setState({changes: 'disabled'});
           }).catch((error) => {
              console.log(error); 
           });
    }

    render() {
      return (
        <div className='login-redirect'>
            <div className='option-grid'>
                <div className='option-header'>
                    <div className='header'>Settings</div>
                    <div className='setting-changes'>{this.state.changes === 'enabled' ? "Unsaved changes": "Settings saved"}</div>
                </div>
                <Inputs 
                    options={this.state.options}
                    input_change={this.handleInputChange}
                />
                <div onClick={this.handleSave} className={'control-button ' + this.state.changes}>
                    <img src="/icons/check.svg" alt="Approve"/>
                    <div className='control-button-text'>
                        Save Changes
                    </div>
                </div>
            </div>
        </div>
      );
    }
  }
  