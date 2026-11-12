import React, { Component, ChangeEvent, KeyboardEvent } from 'react';
// @ts-ignore
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import cookie from '../../cookie';

// @ts-ignore
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import { ALERT_OPTIONS, REGISTER_USER_EXCEPTION_CODE } from '../../constants';

import './style.css';

const MODES = {
  LOGIN: 'LOGIN',
  SIGNUP: 'SIGNUP',
} as const;

type Mode = typeof MODES[keyof typeof MODES];

function getClientId(): string | null {
  console.log(`Using ${process.env.NODE_ENV}`);
  if (process.env.NODE_ENV === 'development') {
    return '231909420850-nj0e0lm27itj46lg5obn78mukuvou6hb.apps.googleusercontent.com';
  }

  if (process.env.NODE_ENV === 'production') {
    return '231909420850-dasbesud6enjf58kgkv38hk7spuieao5.apps.googleusercontent.com';
  }

  return null;
}

interface LogInState {
  email: string;
  username: string;
  password: string;
  confpassword: string;
  mode: Mode;
  errors: Record<string, string>;
}

export default class LogIn extends Component<any, LogInState> {
  msg: any;

  constructor(props: any) {
    super(props);
    document.title = 'Log In - PLynx';
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
      },
    };

    if (cookie.load('user')) {
      cookie.remove('access_token', { path: '/' });
      cookie.remove('refresh_token', { path: '/' });
      cookie.remove('user', { path: '/' });
      cookie.remove('settings', { path: '/' });
      window.location.reload();
    }
  }

  toggleForms() {
    this.setState({
      mode: this.state.mode === MODES.LOGIN ? MODES.SIGNUP : MODES.LOGIN,
    });
  }

  handleLogin() {
    this.loginUser({
      username: this.state.username,
      password: this.state.password,
    });
  }

  showAlert(message: string, type: string) {
    if (this.msg) {
      this.msg.show(message, {
        time: 5000,
        type: 'error',
        icon: <img src={`/alerts/${type}.svg`} width="32" height="32" alt={type} />,
      });
    }
  }

  loginUser({ username, password }: { username: string; password?: string }) {
    PLynxApi.endpoints.token
      .getCustom({
        method: 'get',
        auth: {
          username,
          password: password || '',
        },
      })
      .then((response: any) => {
        cookie.save('access_token', response.data.access_token, { path: '/' });
        cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
        cookie.save('user', response.data.user, { path: '/' });
        cookie.save('settings', response.data.settings, { path: '/' });
        cookie.save('showTour', true, { path: '/' });
        window.location.href = '/workflows';
      })
      .catch((error: any) => {
        this.setState({
          errors: {
            password: 'Username or/and password don`t match',
          },
        });
        console.error(error);
      });
  }

  handleChange(event: ChangeEvent<HTMLInputElement>) {
    this.setState({ [event.target.name]: event.target.value } as any);
  }

  handleKeyPressed(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      const target = event.target as HTMLInputElement;
      if (this.state.mode === MODES.LOGIN && target.name === 'password') {
        this.handleLogin();
      } else {
        this.focusNext(target);
      }
    }
  }

  focusNext(activeInput: HTMLInputElement) {
    activeInput.blur();
    const itemsEl = document.getElementsByClassName('Items')[0];
    if (!itemsEl) return;
    const children = itemsEl.children;
    const activeParent = activeInput.parentNode?.parentNode;
    let next = false;
    for (let i = 0; i < children.length; i++) {
      if (next) {
        const inputToFocus = children[i]?.children[1]?.children[0] as HTMLInputElement | undefined;
        if (inputToFocus) {
          inputToFocus.focus();
        }
        break;
      } else if (children[i] === activeParent) {
        next = true;
      }
    }
  }

  handleLoginCallback(credentialResponse: any) {
    if (!credentialResponse || !credentialResponse.credential) {
      this.showAlert('Failed to authenticate with Google', 'failed');
      return;
    }

    PLynxApi.endpoints.register_with_oauth2
      .create({
        token: credentialResponse.credential,
      })
      .then((oauthResponse: any) => {
        cookie.save('access_token', oauthResponse.data.access_token, { path: '/' });
        cookie.save('refresh_token', oauthResponse.data.refresh_token, { path: '/' });
        cookie.save('user', oauthResponse.data.user, { path: '/' });
        cookie.save('settings', oauthResponse.data.settings, { path: '/' });
        window.location.href = '/workflows';
      })
      .catch((error: any) => {
        if (!error.response) {
          this.showAlert('Failed to register user', 'failed');
          console.error(error);
        } else {
          const errorMessage = (REGISTER_USER_EXCEPTION_CODE as any)[error.response.data.error_code];
          if (errorMessage) {
            this.setState({ errors: errorMessage });
          } else {
            this.showAlert(error.response.data.message, 'failed');
          }
        }
      });
  }

  render() {
    const isLogIn = this.state.mode === MODES.LOGIN;
    const clientId = getClientId();
    let itemDescriptors: Array<{ title: string; name: string; element: React.ReactNode }> = [];
    if (this.state.mode === MODES.LOGIN) {
      itemDescriptors = [
        {
          title: 'Username',
          name: 'username',
          element: (
            <input
              name="username"
              value={this.state.username}
              autoComplete="on"
              onChange={(e) => this.handleChange(e)}
              onKeyDown={(e) => this.handleKeyPressed(e)}
            />
          ),
        },
        {
          title: 'Password',
          name: 'password',
          element: (
            <input
              name="password"
              value={this.state.password}
              autoComplete="on"
              type="password"
              onChange={(e) => this.handleChange(e)}
              onKeyDown={(e) => this.handleKeyPressed(e)}
            />
          ),
        },
      ];
    }

    return (
      <div className="Login">
        <AlertContainer ref={(a: any) => (this.msg = a)} {...ALERT_OPTIONS} />
        <div className="LoginBlock">
          <div className="login-hello-message">Hello! 👋 Please sign in to continue.</div>
          {clientId && (
            <div className="loginButton">
              <GoogleOAuthProvider clientId={clientId}>
                <GoogleLogin
                  text={isLogIn ? 'signin_with' : 'signup_with'}
                  onSuccess={(response: any) => this.handleLoginCallback(response)}
                  onError={() => this.showAlert('Failed to sign in with Google', 'failed')}
                />
              </GoogleOAuthProvider>
            </div>
          )}
          <div className="Items">
            {itemDescriptors.map((item) => (
              <div className="Item" key={item.title}>
                <div className="NameCell">{item.title}</div>
                <div className="ValueCell">{item.element}</div>
                <div className="ErrorCell">{this.state.errors[item.name]}</div>
              </div>
            ))}
          </div>
          <div className="login-notes">
            *If you have any troubles to sign in, please make sure 3rd party cookies are enabled for this website.
          </div>

          {isLogIn && (
            <button className="loginButton" onClick={() => this.handleLogin()}>
              Login
            </button>
          )}

          <div className="toggleState" onClick={() => this.toggleForms()}>
            {isLogIn ? 'Sign Up' : 'Login'}
          </div>
          {isLogIn && (
            <div
              className="forgotPassword"
              onClick={() => this.showAlert("This part wasn't coded in yet...", 'failed')}
            >
              Forgot Password?
            </div>
          )}
        </div>
      </div>
    );
  }
}
