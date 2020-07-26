import React, { Component } from 'react';
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import makePropertiesBox from '../Common/makePropertiesBox';
import ParameterItem from '../Common/ParameterItem';
import { ALERT_OPTIONS } from '../../constants';
import cookie from 'react-cookies';

import './style.css';

export default class LogIn extends Component {
  constructor(props) {
    super(props);
    document.title = "Users - PLynx";
    this.state = {
      user: null,
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
      console.log(name, value);
  }

  render() {

    const userSettingsList = [
        <ParameterItem
          name={'parameter.name'}
          widget={'parameter.widget'}
          value={'parameter.value'}
          parameterType={'str'}
          key={1}
          readOnly={false}
          onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
          onLinkClick={(name) => this.handleLinkClick(name)}
          />
    ];
    return (
      <div className='user-view-window'>
        <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
        <div className='user-view-block'>
          {makePropertiesBox('User', userSettingsList)}
          <div className='Items'>
            <div className='Item'>
              <div className='NameCell'>
                Username
              </div>
              <div className='ValueCell'>
                <input name='username'
                       value={this.state.username}
                       autoComplete="on"
                       onChange={(e) => this.handleChange(e)}
                       onKeyPress={(e) => this.handleKeyPressed(e)}
                       />
              </div>
            </div>

            <div className='Item'>
              <div className='NameCell'>
                Password
              </div>
              <div className='ValueCell'>
                <input name='password'
                       value={this.state.password}
                       autoComplete="on"
                       type="password"
                       onChange={(e) => this.handleChange(e)}
                       onKeyPress={(e) => this.handleKeyPressed(e)}
                       />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
