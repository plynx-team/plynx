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
      mode: 0,
      errors: {
        email: '',
        username: '',
        password: '',
        confpassword: '',
      }
    };

    if (cookie.load('user')) {
      cookie.remove('access_token', { path: '/' });
      cookie.remove('refresh_token', { path: '/' });
      cookie.remove('user', { path: '/' });
      cookie.remove('settings', { path: '/' });
      window.location.reload(false);
    }
  }

  toggleForms(MODES) {
    var m;
    (this.state.mode === MODES.LOGIN) ? m = MODES.REGISTER : m = MODES.LOGIN
    this.setState({ mode: m });
    console.log(m)
  }

  handleButton(MODES) {
    if (this.state.mode === MODES.LOGIN) {
      this.handleLogin();
    } else if (this.state.mode === MODES.REGISTER) {
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
    if (this.state.password !== this.state.confpassword) {
      var dic = this.state.errors;
      dic.confpassword = "Password and confirmation must match";
      this.setState({ errors: dic });
    } else {
      this.registerUser ({
        email: this.state.email,
        username: this.state.username,
        password: this.state.password,
      })
    }
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
      cookie.save('user', response.data.user, { path: '/' });
      cookie.save('settings', response.data.settings, { path: '/' });
      window.location = '/workflows';
    })
    .catch((error) => {
      this.showAlert('Failed authenticate user', 'failed');
      console.error(error);
    });
  }

  registerUser({ email, username, password }) {
    PLynxApi.endpoints.register.create({
      email: email,
      username: username,
      password: password,
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
        dic['email'] = response.data.emailError;
        dic['username'] = response.data.usernameError;
        dic['password'] = response.data.passwordError;
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

  handleKeyPressed(event, MODES) {
    if (event.key === 'Enter') {
      if (this.state.mode === MODES.LOGIN && event.target.name === 'password') {
        this.handleLogin();
      } else if (event.target.name === 'confpassword') {
        this.handleRegister();
      } else {
        this.focusNext(event.target);
      }
    }
  }

  focusNext(activeInput) {
    activeInput.blur();
    var children = document.getElementsByClassName('Items')[0].children;
    var activeinput = activeInput.parentNode.parentNode;
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

  render() {
    const MODES = { "LOGIN": 0, 'REGISTER': 1 }

    return (
      <div className='Login'>
        <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
        <div className='LoginBlock'>
          <div className='Items'>
          {this.state.mode === MODES.REGISTER &&
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
                        onKeyPress={(e) => this.handleKeyPressed(e, MODES)}
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
                       onKeyPress={(e) => this.handleKeyPressed(e, MODES)}
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
                       onKeyPress={(e) => this.handleKeyPressed(e, MODES)}
                       />
              </div>
              <div className="ErrorCell">
                {this.state.errors.password}
              </div>
            </div>

            {this.state.mode === MODES.REGISTER &&
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
                        onKeyPress={(e) => this.handleKeyPressed(e, MODES)}
                        />
                </div>
                <div className="ErrorCell">
                  {this.state.errors.confpassword}
                </div>
              </div>
            }
          </div>
            <button className="loginButton" onClick={() => this.handleButton(MODES)} href="#">
            {this.state.mode === MODES.LOGIN ? 'Login': 'Register'}
            </button>
              <div className="toggleState" onClick={() => this.toggleForms(MODES)}>
                {this.state.mode === MODES.LOGIN ? 'Register': 'Login'}
              </div>
              {this.state.mode === MODES.LOGIN &&
                <div className="forgotPassword" onClick={() => this.showAlert("This part wasn't codded in yet...", "failed")}>
                  Forgot Password?
                </div>
              }
        </div>
      </div>
    );
  }
}
