import React, { Component } from 'react';
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import { ALERT_OPTIONS } from '../../constants';
import cookie from 'react-cookies';

import './style.css';

export default class LogIn extends Component {
  constructor(props) {
    super(props);
    document.title = "Log In - PLynx";
    this.state = {
      email: '',
      username: '',
      password: '',
      confpassword: '',
      login: true,
      errors: {
        email: '',
        username: '',
        password: '',
        confpassword: '',
      }
    };

    if (cookie.load('username')) {
      cookie.remove('access_token', { path: '/' });
      cookie.remove('refresh_token', { path: '/' });
      cookie.remove('username', { path: '/' });
      window.location.reload(false);
    }
  }

  toggleForms() {
    this.setState({ login: !this.state.login });
  }

  handleButton() {
    if (this.state.login) {
      this.handleLogin();
    } else {
      this.handleRegister();
    }
  }

  handleLogin() {
    console.log("Login");
    this.loginUser({
      username: this.state.username,
      password: this.state.password
    });
  }

  handleRegister() {
    this.registerUser ({
      email: this.state.email,
      username: this.state.username,
      password: this.state.password,
      confpassword: this.state.confpassword
    })
  }

  showAlert(message, type) {
    this.msg.show(message, {
      time: 5000,
      type: 'error',
      icon: <img src={"/alerts/" + type + ".svg"} width="32" height="32" alt={type} />
    });
  }

  loginUser({ username, password }) {
    PLynxApi.endpoints.token.getCustom({
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
      window.location = '/workflows';
    })
    .catch((error) => {
      this.showAlert('Failed authenticate user', 'failed');
      console.error(error);
    });
  }

  registerUser({ email, username, password, confpassword }) {
    PLynxApi.endpoints.register.getCustom({
      method: 'post',
      headers: {
        email: email,
        username: username,
        password: password,
        confpassword: confpassword,
      }
    })
    .then(response => {
      console.log(response.data);
      if (response.data.success) {
        console.log('Registered');
        cookie.save('access_token', response.data.access_token, { path: '/' });
        cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
        cookie.save('username', username, { path: '/' });
        window.location = '/workflows';
      } else {
        var dic = this.state.errors
        for (var key in response.data) {
          if (key !== 'success') {
            dic[key] = response.data[key]
          }
        }
        this.setState({ errors: dic });
        this.showAlert('Failed user registration', 'failed');
      }
    })
    .catch((error) => {
      this.showAlert('Failed user registration', 'failed');
      console.error(error);
    });
  }

  handleChange(event) {
    this.setState({[event.target.name]: event.target.value});
  }

  handleKeyPressed(event) {
    if (event.key === 'Enter') {
      if (this.state.login && event.target.name === 'password') {
        this.handleLogin();
      } else if (event.target.name === 'confpassword') {
        this.handleRegister();
      } else {
        event.target.blur();
        var children = document.getElementsByClassName('Items')[0].children;
        var activeinput = event.target.parentNode.parentNode;
        var next = false;
        for (var i = 0; i < children.length; i++) {
          if (next) {
            children[i].children[1].children[0].focus();
            return -1
          } else if (children[i] === activeinput) {
            next = true;
          }
        }
        
      }
    }
  }

  render() {
    return (
      <div className='Login'>
        <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
        <div className='LoginBlock'>
          <div className='Items'>
          {!this.state.login &&
            <div className='Item'>
                <div className='NameCell'>
                  Email
                </div>
                <div className='ValueCell'>
                  <input name='email'
                        value={this.state.email}
                        autoComplete="on"
                        type="email"
                        onChange={(e) => this.handleChange(e)}
                        onKeyPress={(e) => this.handleKeyPressed(e)}
                        />
                </div>
                <div className="ErrorCell">
                  {this.state.errors.email}
                </div>
              </div>
            }

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
              <div className="ErrorCell">
                {this.state.errors.username}
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
              <div className="ErrorCell">
                {this.state.errors.password}
              </div>
            </div>

            {!this.state.login &&
            <div className='Item'>
                <div className='NameCell'>
                  Confirm Password
                </div>
                <div className='ValueCell'>
                  <input name='confpassword'
                        value={this.state.confpassworf}
                        autoComplete="on"
                        type="password"
                        onChange={(e) => this.handleChange(e)}
                        onKeyPress={(e) => this.handleKeyPressed(e)}
                        />
                </div>
                <div className="ErrorCell">
                  {this.state.errors.confpassword}
                </div>
              </div>
            }
          </div>
            <button className="loginButton" onClick={() => this.handleButton()} href="#">
            {this.state.login ? 'Login': 'Register'}
            </button>
              <div className="toggleState" onClick={() => this.toggleForms()}>
                {this.state.login ? 'Register': 'Login'}
              </div>
              {this.state.login &&
                <div className="forgotPassword" onClick={() => this.showAlert("This part wasn't codded in yet...", "failed")}>
                  Forgot Password?
                </div>
              }
        </div>
      </div>
    );
  }
}
