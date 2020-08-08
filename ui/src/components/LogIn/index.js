import React, { Component } from 'react';
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import { ALERT_OPTIONS, USER_POST_ACTION, REGISTER_USER_EXCEPTION_CODE } from '../../constants';
import { validatePassword } from '../Common/passwordUtils';
import cookie from 'react-cookies';

import './style.css';

const MODES = {
  "LOGIN": 'LOGIN',
  'SIGNUP': 'SIGNUP',
};


export default class LogIn extends Component {
  constructor(props) {
    super(props);
    document.title = "Log In - PLynx";
    this.state = {
      email: '',
      username: '',
      password: '',
      confpassword: '',
      mode: MODES.LOGIN,
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

  toggleForms() {
    this.setState({
      mode: this.state.mode === MODES.LOGIN ? MODES.SIGNUP : MODES.LOGIN
    });
  }

  handleButton() {
    if (this.state.mode === MODES.LOGIN) {
      this.handleLogin();
    } else if (this.state.mode === MODES.SIGNUP) {
      this.handleSignup();
    }
  }

  handleLogin() {
    console.log("Login");
    this.loginUser({
      username: this.state.username,
      password: this.state.password
    });
  }

  handleSignup() {
    if (this.state.password !== this.state.confpassword) {
      this.setState({
        errors: {
          confpassword: "Password and confirmation must match"
        }
      });
    } else if (!validatePassword(this.state.password)) {
      this.setState({
        errors: {
          password: 'Password must have at least 8 characters, including an uppercase letter and a number'
        }
      });
    } else {
      this.signupUser({
        email: this.state.email,
        username: this.state.username,
        password: this.state.password,
      });
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
      this.setState({
        errors: {
          password: 'Username or/and password don`t match'
        }
      });
      console.error(error);
    });
  }

  signupUser({ email, username, password }) {
    PLynxApi.endpoints.register.create({
      action: USER_POST_ACTION.MODIFY,
      user: this.user,
      old_password: this.oldPassword,
      new_password: this.newPassword,

      email: email,
      username: username,
      password: password,
    })
    .then(response => {
      console.log('Registered');
      cookie.save('access_token', response.data.access_token, { path: '/' });
      cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
      cookie.save('user', response.data.user, { path: '/' });
      cookie.save('settings', response.data.settings, { path: '/' });
      window.location = '/workflows';
    })
    .catch((error) => {
      if (!error.response) {
        this.showAlert('Failed to register user', 'failed');
        console.error(error);
      } else {
        const response = error.response;
        const errorMessage = REGISTER_USER_EXCEPTION_CODE[response.data.error_code];
        if (errorMessage) {
          this.setState({errors: errorMessage});
        } else {
          this.showAlert(response.data.message, 'failed');
        }
      }
    });
  }

  handleChange(event) {
    this.setState({[event.target.name]: event.target.value});
  }

  handleKeyPressed(event) {
    if (event.key === 'Enter') {
      if (this.state.mode === MODES.LOGIN && event.target.name === 'password') {
        this.handleLogin();
      } else if (event.target.name === 'confpassword') {
        this.handleSignup();
      } else {
        this.focusNext(event.target);
      }
    }
  }

  focusNext(activeInput) {
    activeInput.blur();
    const children = document.getElementsByClassName('Items')[0].children;
    const activeinput = activeInput.parentNode.parentNode;
    let next = false;
    for (let i = 0; i < children.length; i++) {
      if (next) {
        children[i].children[1].children[0].focus();
      } else if (children[i] === activeinput) {
        next = true;
      }
    }
  }

  render() {
    let itemDescriptors = [];
    if (this.state.mode === MODES.SIGNUP) {
      itemDescriptors = [
        {
          title: 'Email',
          name: 'email',
          element:
                  <input name='email'
                      value={this.state.email}
                      autoComplete="on"
                      type="email"
                      onChange={(e) => this.handleChange(e)}
                      onKeyPress={(e) => this.handleKeyPressed(e)}
                      />,
        }, {
          title: 'Username',
          name: 'username',
          element:
                  <input name='username'
                       value={this.state.username}
                       autoComplete="on"
                       onChange={(e) => this.handleChange(e)}
                       onKeyPress={(e) => this.handleKeyPressed(e)}
                       />,
        }, {
          title: 'Password',
          name: 'password',
          element:
                  <input name='password'
                       value={this.state.password}
                       autoComplete="on"
                       type="password"
                       onChange={(e) => this.handleChange(e)}
                       onKeyPress={(e) => this.handleKeyPressed(e)}
                       />
        }, {
          title: 'Confirm Password',
          name: 'confpassword',
          element:
                  <input name='confpassword'
                      value={this.state.confpassworf}
                      autoComplete="on"
                      type="password"
                      onChange={(e) => this.handleChange(e)}
                      onKeyPress={(e) => this.handleKeyPressed(e)}
                      />,
        },
      ];
    } else if (this.state.mode === MODES.LOGIN) {
      itemDescriptors = [
        {
          title: 'Username',
          name: 'username',
          element:
                  <input name='username'
                       value={this.state.username}
                       autoComplete="on"
                       onChange={(e) => this.handleChange(e)}
                       onKeyPress={(e) => this.handleKeyPressed(e)}
                       />,
        }, {
          title: 'Password',
          name: 'password',
          element:
                  <input name='password'
                       value={this.state.password}
                       autoComplete="on"
                       type="password"
                       onChange={(e) => this.handleChange(e)}
                       onKeyPress={(e) => this.handleKeyPressed(e)}
                       />
        },
      ];
    }


    return (
      <div className='Login'>
        <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
        <div className='LoginBlock'>
          <div className='Items'>
            {itemDescriptors.map(item => <div
                    className='Item'
                    key={item.title}
                >
                    <div className='NameCell'>
                      {item.title}
                    </div>
                    <div className='ValueCell'>
                      {item.element}
                    </div>
                    <div className="ErrorCell">
                      {this.state.errors[item.name]}
                    </div>
                  </div>
            )}


          </div>

          <button className="loginButton" onClick={() => this.handleButton()} href="#">
            {this.state.mode === MODES.LOGIN ? 'Login' : 'Sign Up'}
          </button>

          <div className="toggleState" onClick={() => this.toggleForms()}>
            {this.state.mode === MODES.LOGIN ? 'Sign Up' : 'Login'}
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
