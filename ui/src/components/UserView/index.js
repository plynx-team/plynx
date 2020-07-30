import React, { Component } from 'react';
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import APIObject from '../Common/APIObject';
import makePropertiesBox from '../Common/makePropertiesBox';
import ParameterItem from '../Common/ParameterItem';
import { ALERT_OPTIONS, COLLECTIONS } from '../../constants';
import { User } from 'react-feather';
import cookie from 'react-cookies';

import './style.css';

export default class LogIn extends Component {
  constructor(props) {
    super(props);
    document.title = "Users - PLynx";
    this.user = {
        username: '',
        display_name: '',
        settings: {
            node_view_mode: 1,
        },

    };
    this.state = {
      user: this.user,
    };
  }

  showAlert(message, type) {
    this.msg.show(message, {
      time: 5000,
      type: 'error',
      icon: <img src={"/alerts/" + type + ".svg"} width="32" height="32" alt={type} />
    });
  }



  handleChange(event) {
    this.setState({[event.target.name]: event.target.value});
  }

  handleKeyPressed(event) {
    if (event.key === 'Enter') {
      this.handleLogin();
    }
  }

  handleParameterChanged(name, value) {
    this.user[name] = value;
    this.setState({
        user: this.user
    })
  }

  loadUser(user) {
    this.user = user;
    this.setState({
      user: this.user,
    });
  }

  render() {
    const username = this.props.match.params.username.replace(/\$+$/, '');
    let keyCounter = 0;

    const personalSettingsList = [
        <ParameterItem
            name={'username'}
            widget={'Username'}
            value={this.state.user.username}
            parameterType={'str'}
            key={(++keyCounter) + this.state.user.username}
            readOnly={true}
            onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
            onLinkClick={(name) => this.handleLinkClick(name)}
          />,
        <ParameterItem
            name={'display_name'}
            widget={'Display Name'}
            value={this.state.user.display_name}
            parameterType={'str'}
            key={(++keyCounter)}
            readOnly={false}
            onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
            />,
    ];
    const passwordSettingsList = [
        <ParameterItem
            name={'old_password'}
            widget={'Old password'}
            value={this.state.old_password}
            parameterType={'password'}
            key={(++keyCounter)}
            readOnly={false}
            onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
            onLinkClick={(name) => this.handleLinkClick(name)}
          />,
        <ParameterItem
            name={'new_password'}
            widget={'New password'}
            value={this.state.new_password}
            parameterType={'password'}
            key={(++keyCounter)}
            readOnly={false}
            onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
            />,
        <ParameterItem
            name={'new_password_retype'}
            widget={'New password retype'}
            value={this.state.new_password}
            parameterType={'password'}
            key={(++keyCounter)}
            readOnly={false}
            onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
            />,
    ];
    return (
      <div className='user-view-window'>
        <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
        <APIObject
            collection={COLLECTIONS.USERS}
            object_id={username}
            onUpdateData={data => {this.loadUser(data.user)}}
        />
        <div className='user-view-block'>
          <div className='user-preview'>
            <User className='user-icon' />
            <div>
              {this.state.user.display_name ? this.state.user.display_name : this.state.user.username}
            </div>
          </div>
          {makePropertiesBox('Personal Settings', personalSettingsList)}
          {makePropertiesBox('Change Password', passwordSettingsList)}
        </div>
      </div>
    );
  }
}
