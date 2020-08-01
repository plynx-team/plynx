import React, { Component } from 'react';
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import APIObject from '../Common/APIObject';
import makePropertiesBox from '../Common/makePropertiesBox';
import ParameterItem from '../Common/ParameterItem';
import { ALERT_OPTIONS, COLLECTIONS, IAM_POLICIES } from '../../constants';
import { User } from 'react-feather';
import cookie from 'react-cookies';

import './style.css';

export default class LogIn extends Component {
  constructor(props) {
    super(props);
    document.title = "Users - PLynx";
    this.user = {
        username: '',
        node_view_mode: {values: ['1'], index: 0},
        display_name: '',
        policies: 0,
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

  handleParameterChange(name, value) {
    this.user[name] = value;
    this.setState({
        user: this.user
    })
  }

  handlePolicyChange(name, value) {
    if (value) {
      this.user.policies = this.user.policies | IAM_POLICIES[name];
    } else {
      this.user.policies = this.user.policies & (~IAM_POLICIES[name]);
    }
    this.setState({
        user: this.user
    });
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
            onParameterChanged={(name, value) => this.handleParameterChange(name, value)}
          />,
        <ParameterItem
            name={'display_name'}
            widget={'Display Name'}
            value={this.state.user.display_name}
            parameterType={'str'}
            key={(++keyCounter)}
            readOnly={false}
            onParameterChanged={(name, value) => this.handleParameterChange(name, value)}
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
            onParameterChanged={(name, value) => this.handleParameterChange(name, value)}
          />,
        <ParameterItem
            name={'new_password'}
            widget={'New password'}
            value={this.state.new_password}
            parameterType={'password'}
            key={(++keyCounter)}
            readOnly={false}
            onParameterChanged={(name, value) => this.handleParameterChange(name, value)}
            />,
        <ParameterItem
            name={'new_password_retype'}
            widget={'New password retype'}
            value={this.state.new_password}
            parameterType={'password'}
            key={(++keyCounter)}
            readOnly={false}
            onParameterChanged={(name, value) => this.handleParameterChange(name, value)}
            />,
    ];
    const viewSettingsList = [
        <ParameterItem
            name={'node_view_mode'}
            widget={'Node view settings'}
            value={this.state.user.node_view_mode}
            parameterType={'enum'}
            key={(++keyCounter) + this.state.user.node_view_mode.index}
            readOnly={false}
            onParameterChanged={(name, value) => this.handleParameterChange(name, value)}
          />,
    ];

    const iamSettingsList = Object.entries(IAM_POLICIES).map((policy_tuple, index) =>
        <ParameterItem
            name={policy_tuple[0]}
            widget={policy_tuple[0]}
            value={this.state.user.policies & policy_tuple[1] > 0}
            parameterType={'bool'}
            key={(++keyCounter) + this.state.user.username + policy_tuple[0]}
            readOnly={false}
            onParameterChanged={(name, value) => this.handlePolicyChange(name, value)}
          />
      );

    return (
      <div className='user-view-content'>
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
          {makePropertiesBox('View Settings', viewSettingsList)}
          {makePropertiesBox('IAM Policies Settings', iamSettingsList)}
        </div>
      </div>
    );
  }
}
