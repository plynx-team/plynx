import React, { Component } from 'react';
import cookie from 'react-cookies';
import { GoogleLogin } from 'react-google-login';
import { gapi } from 'gapi-script';

import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import { ALERT_OPTIONS, USER_POST_ACTION, REGISTER_USER_EXCEPTION_CODE } from '../../constants';
import { validatePassword } from '../Common/passwordUtils';

import './style.css';

const MODES = {
  "LOGIN": 'LOGIN',
  'SIGNUP': 'SIGNUP',
};


function getClientId() {
  console.log(`Using ${process.env.NODE_ENV}`);
  if (process.env.NODE_ENV === 'development') {
    return "231909420850-nj0e0lm27itj46lg5obn78mukuvou6hb.apps.googleusercontent.com";
  }

  if (process.env.NODE_ENV === 'production') {
    return "231909420850-dasbesud6enjf58kgkv38hk7spuieao5.apps.googleusercontent.com";
  }

  return null;
}


export default class LogIn extends Component {
  constructor(props) {
    super(props);
    document.title = "Log In - PLynx";
    this.state = {
      email: '',
      username: '',
      password: '',
      confpassword: '',
      mode: MODES.SIGNUP,
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

    const initClient = () => {
        gapi.client.init({
        clientId: getClientId(),
        scope: "https://www.googleapis.com/auth/userinfo.email"
      });
    };
    gapi.load('client:auth2', initClient);
  }

  toggleForms() {
    this.setState({
      mode: this.state.mode === MODES.LOGIN ? MODES.SIGNUP : MODES.LOGIN
    });
  }

  handleLogin() {
    console.log("Login");
    this.loginUser({
      username: this.state.username,
      password: this.state.password
    });
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
      cookie.save('showTour', true, { path: '/' });
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

  handleChange(event) {
    this.setState({[event.target.name]: event.target.value});
  }

  handleKeyPressed(event) {
    if (event.key === 'Enter') {
      if (this.state.mode === MODES.LOGIN && event.target.name === 'password') {
        this.handleLogin();
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

  handleLoginCallback(response) {

    PLynxApi.endpoints.register_with_oauth2.create({
      token: response.tokenId,
    })
    .then(response => {
      console.log(response);

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

  render() {
    const isLogIn = this.state.mode === MODES.LOGIN;
    let itemDescriptors = [];
    if (this.state.mode === MODES.SIGNUP) {
      itemDescriptors = [];
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
          <div className="login-hello-message">
            Hello! 👋 Please sign in to continue.
          </div>
          <GoogleLogin
            clientId={getClientId()}
            buttonText={isLogIn ? "Log in with Google" : "Sign up with Google"}
            onSuccess={response => this.handleLoginCallback(response)}
            onFailure={this.handleLoginCallback}
            cookiePolicy={'single_host_origin'}
            className="loginButton"
          />
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
          <div className="login-notes">
            *If you have any troubles to sign in, please make sure 3rd party coockies are enabled for this website.
          </div>

          {isLogIn &&
            <button className="loginButton" onClick={() => this.handleLogin()} href="#">
              Login
            </button>
          }

          <div className="toggleState" onClick={() => this.toggleForms()}>
            {isLogIn ? 'Sign Up' : 'Login'}
          </div>
          {isLogIn &&
            <div className="forgotPassword" onClick={() => this.showAlert("This part wasn't codded in yet...", "failed")}>
                Forgot Password?
            </div>
          }

        </div>
      </div>
    );
  }
}
