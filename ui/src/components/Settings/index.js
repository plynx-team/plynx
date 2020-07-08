import React, { Component } from 'react';
import cookie from 'react-cookies';
import { API_ENDPOINT } from '../../configConsts';

import Inputs from './Inputs';

import './style.css';
import { PLynxApi } from '../../API';

export default class Settings extends Component {
    constructor(props) {
        super(props);

        this.state = {
            options: props.options,
            changes: 'disabled',
        };

        this.headerRef = props.headerRef;

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
              this.props.saveFunc(value_obj, this.headerRef);
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
  