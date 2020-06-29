import React, { Component } from 'react';

import Inputs from './Inputs';

import './style.css';
import { PLynxApi } from '../../API';

export default class Settings extends Component {
    constructor(props) {
        super(props);

        this.state = {
            options: [
                {   
                    title: 'Theme',
                    type: 'list',
                    values: ['one', 'two', 'three'],
                    choice: 'three'
                },
                {   
                    title: 'Github',
                    type: 'boolean',
                    choice: true,
                },
                {   
                    title: 'Docs',
                    type: 'boolean',
                    choice: false,
                },
            ],
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

        for (var i in this.state.options) {
            var inp_title = this.state.options[i].title;
            if (e.target.className.includes('boolean-input')) {
                main_title = e.target.className.replace('boolean-input-', '');
                if (inp_title === main_title) {
                    dic[i].choice = !dic[i].choice;
                    break
                }
            } else if (e.target.className.includes('list-input')) {
                main_title = e.target.className.replace('list-input-', '');
                if (inp_title === main_title) {
                    dic[i].choice = e.target.value;
                    break
                }
            }
            this.setState({options:dic});
        }
    }

    handleSave = () => {
        console.log('bassed')
    }

    render() {
      return (
        <div className='login-redirect'>
            <div className='option-grid'>
                <div className='option-header'>
                    <div onClick={PLynxApi.demo.test.testval()} className='header'>Settings</div>
                    <div className='setting-changes'>{this.state.changes === 'enabled' ? "unsaved changes": "setting saved"}</div>
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
  