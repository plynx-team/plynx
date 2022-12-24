import React, { Component } from 'react';
import APIObject from '../Common/APIObject';
import PropTypes from 'prop-types';
import makePropertiesBox from '../Common/makePropertiesBox';
import ParameterItem from '../Common/ParameterItem';
import { makeControlPanel, makeControlButton } from '../Common/controlButton';
import { COLLECTIONS, IAM_POLICIES, USER_POST_ACTION, RESPONCE_STATUS } from '../../constants';
import { validatePassword } from '../Common/passwordUtils';
import { User } from 'react-feather';
import cookie from 'react-cookies';

import './style.css';

export default class LogIn extends Component {
  static propTypes = {
    match: PropTypes.shape({
      params: PropTypes.shape({
        username: PropTypes.string.isRequired
      }),
    }),
  };

  constructor(props) {
    super(props);
    document.title = "Users - PLynx";
    this.user = {
      username: '',
      settings: {
        display_name: '',
      },
      policies: [],
      _is_admin: false,
      _readonly: true,
    };
    this.state = {
      user: this.user,
      oldPassword: '',
      newPassword: '',
      confirmNewPassword: '',
    };
  }

  handleParameterChange(name, value) {
    this.user[name] = value;
    this.setState({
      user: this.user
    });
  }

  handleSettingsChange(name, value) {
    this.user.settings[name] = value;
    this.setState({
      user: this.user
    });
  }

  handleChange(name, value) {
    this[name] = value;
    this.setState({
      name: value
    });
  }

  handlePolicyChange(name, value) {
    if (value) {
      this.user.policies.push(name);
    } else {
      this.user.policies = this.user.policies.filter((policy) => policy !== name);
    }
    console.log(this.user.policies);
    this.setState({
      user: this.user
    });
  }

  loadUser(user) {
    this.user = user;
    console.log('resp', user);
    this.setState({
      user: this.user,
    });
  }

  handleSave() {
    if (this.oldPassword && this.newPassword !== this.confirmNewPassword) {
      this.apiObject.showAlert('New passwords don`t match', 'failed');
      return;
    }
    if (this.oldPassword && !validatePassword(this.newPassword)) {
      this.apiObject.showAlert('Password must have at least 8 characters, including an uppercase letter and a number', 'failed');
      return;
    }
    if (!this.oldPassword && (this.newPassword || this.confirmNewPassword)) {
      this.apiObject.showAlert('Please enter `old password`', 'failed');
      return;
    }
    this.apiObject.postData({
      action: USER_POST_ACTION.MODIFY,
      user: this.user,
      old_password: this.oldPassword,
      new_password: this.newPassword,
    });
  }

  handlePostResponse(data) {
    if (data.status === RESPONCE_STATUS.SUCCESS) {
      this.apiObject.showAlert('Saved', 'success');
      const refresh = cookie.load('user').username === data.user.username;
      cookie.save('user', data.user, { path: '/' });
      console.log('settings', data.settings);
      cookie.save('settings', data.settings, { path: '/' });
      if (refresh) {
        // Need to reload header if this is the current user
        window.location.reload(false);
      }
    } else {
      this.apiObject.showAlert(data.message, 'failed');
    }
  }

  makeControls() {
    const items = [
      {
        render: makeControlButton,
        props: {
          img: 'save.svg',
          text: 'Save',
          enabled: !this.state.user._readonly,
          func: () => this.handleSave(),
        },
      },
    ];

    return makeControlPanel(
      {
        props: {
          items: items,
          key: 'control',
        },
      });
  }

  render() {
    const username = this.props.match.params.username.replace(/\$+$/, '');
    let keyCounter = 0;

    const accountSettingsList = [
      <ParameterItem
            name={'username'}
            widget={'Username'}
            value={this.state.user.username}
            parameterType={'str'}
            key={[(++keyCounter), this.state.user._readonly].join('')}
            readOnly
            onParameterChanged={(name, value) => this.handleParameterChange(name, value)}
          />,
    ];
    const passwordSettingsList = [
      <ParameterItem
            name={'oldPassword'}
            widget={'Old password'}
            value={this.state.oldPassword}
            parameterType={'password'}
            key={[(++keyCounter), this.state.user._readonly].join('')}
            readOnly={this.state.user._readonly}
            onParameterChanged={(name, value) => this.handleChange(name, value)}
          />,
      <ParameterItem
            name={'newPassword'}
            widget={'New password'}
            value={this.state.newPassword}
            parameterType={'password'}
            key={[(++keyCounter), this.state.user._readonly].join('')}
            readOnly={this.state.user._readonly}
            onParameterChanged={(name, value) => this.handleChange(name, value)}
            />,
      <ParameterItem
            name={'confirmNewPassword'}
            widget={'Confirm new password'}
            value={this.state.confirmNewPassword}
            parameterType={'password'}
            key={[(++keyCounter), this.state.user._readonly].join('')}
            readOnly={this.state.user._readonly}
            onParameterChanged={(name, value) => this.handleChange(name, value)}
            />,
    ];
    const personalSettingsList = [
      <ParameterItem
            name={'display_name'}
            widget={'Display Name'}
            value={this.state.user.settings.display_name}
            parameterType={'str'}
            key={[(++keyCounter), this.state.user._readonly].join('')}
            readOnly={this.state.user._readonly}
            onParameterChanged={(name, value) => this.handleSettingsChange(name, value)}
            />,
    ];
    const iamSettingsList = Object.entries(IAM_POLICIES).map((policy_tuple) => <ParameterItem
            name={policy_tuple[0]}
            widget={policy_tuple[0]}
            value={this.state.user.policies.indexOf(policy_tuple[1]) >= 0}
            parameterType={'bool'}
            key={[(++keyCounter), this.state.user._readonly, this.state.user.username, policy_tuple[0]].join('')}
            readOnly={!this.state.user._is_admin}
            onParameterChanged={(name, value) => this.handlePolicyChange(name, value)}
          />
      );

    return (
      <div className='user-view-content'>
        <APIObject
            collection={COLLECTIONS.USERS}
            object_id={username}
            onUpdateData={data => {
              this.loadUser(data.user);
            }}
            onPostResponse={data => {
              this.handlePostResponse(data);
            }}
            ref={a => this.apiObject = a}
        />
        <div className='user-view-block'>
          <div className='user-preview'>
            {
              this.state.user.settings.picture &&
              <img src={this.state.user.settings.picture} className="user-icon" alt="Google profile pic" referrerPolicy="no-referrer"/>
            }
            {
              !this.state.user.settings.picture && <User className='user-icon' />
            }
            <div className="user-display-name">
              {this.state.user.settings.display_name ? this.state.user.settings.display_name : this.state.user.username}
            </div>
          </div>
          {makePropertiesBox('Account Settings', accountSettingsList)}
          <form>
            {makePropertiesBox('Change Password', passwordSettingsList)}
          </form>
          {makePropertiesBox('Personal Settings', personalSettingsList)}
          {makePropertiesBox('IAM Policies Settings', iamSettingsList)}

          {this.makeControls()}
        </div>
      </div>
    );
  }
}
