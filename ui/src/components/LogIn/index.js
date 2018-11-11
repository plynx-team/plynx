// src/components/NotFound/index.js
import React, { Component } from 'react';
import { PlynxApi } from '../../API.js';
import Button from 'react-toolbox/lib/button/Button'
import cookie from 'react-cookies'

import './style.css';

export default class LogIn extends Component {
  constructor(props) {
    super(props);
    document.title = "Log In - Plynx";
    this.state = {
      username: '',
      password: ''
    }

    if (cookie.load('username')) {
      cookie.remove('access_token', { path: '/' });
      cookie.remove('refresh_token', { path: '/' });
      cookie.remove('username', { path: '/' });
      window.location.reload(false);
    }
  }

  handleLogin() {
    console.log("Login");
    this.loginUser({
      username: this.state.username,
      password: this.state.password
    });
  }

  loginUser({ username, password }) {
    PlynxApi.endpoints.token.getCustom({
        method: 'get',
        auth:
              {
                username: username,
                password: password
              }
      })
    .then(response => {
      cookie.save('access_token', response.data.access_token, { path: '/' });
      cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
      cookie.save('username', username, { path: '/' });
      //dispatch({ type: AUTH_USER });
      //window.location.href = CLIENT_ROOT_URL + '/dashboard';
      window.location = '/graphs';
    })
    .catch((error) => {
      //errorHandler(dispatch, error.response, AUTH_ERROR)
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

  render() {
    return (
      <div className='Login'>
        <div className='LoginBlock'>
          <h1>
            Login
          </h1>

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
          <div className="buttons">
            <Button label="Login" className="loginButton"  onClick={() => this.handleLogin()}/>
          </div>
        </div>
      </div>
    );
  }
}
