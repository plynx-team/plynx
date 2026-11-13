import React, { Component } from 'react';
import { PLynxApi } from '../../api';
import { SimpleLoader } from '../LoadingScreen';
import { SPECIAL_USERS, DEFAULT_WORKFLOW_KIND } from '../../constants';
import cookie from '../../cookie';

import './style.css';

export interface LogInRedirectProps {
  specialUser: string;
  maxTry: number;
}

interface LogInRedirectState {
  errorText: string;
}

export default class LogInRedirect extends Component<LogInRedirectProps, LogInRedirectState> {
  constructor(props: LogInRedirectProps) {
    super(props);
    document.title = 'PLynx';

    this.state = {
      errorText: '',
    };
  }

  componentDidMount() {
    this.loginUser(this.props.specialUser);
  }

  sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async loginUser(specialUser: string) {
    const loading = true;
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;
    let maxTry = this.props.maxTry;

    let handleResponse: ((response: any) => void) | null = null;
    let promise: any = null;

    if (specialUser === SPECIAL_USERS.DEFAULT) {
      promise = PLynxApi.endpoints.token.getCustom({
        method: 'get',
        auth: {
          username: SPECIAL_USERS.DEFAULT,
          password: '',
        },
      });
      handleResponse = (response: any) => {
        window.location.href = '/workflows';
        if (!cookie.load('access_token')) {
          cookie.save('showTour', true, { path: '/' });
          window.location.href = `/templates/${DEFAULT_WORKFLOW_KIND}`;
        }
        cookie.save('access_token', response.data.access_token, { path: '/' });
        cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
        cookie.save('user', response.data.user, { path: '/' });
        cookie.save('settings', response.data.settings, { path: '/' });
      };
    } else if (specialUser === SPECIAL_USERS.REDIRECT) {
      window.location.href = '/workflows/';
      return;
    }

    const errorHandler = (error: any) => {
      maxTry -= 1;
      if (maxTry < 0) {
        window.location.href = '/login';
      }
      this.setState({ errorText: error.message });
    };

    while (loading && promise) {
      await promise.then(handleResponse).catch(errorHandler);
      if (loading) {
        await this.sleep(sleepPeriod);
        sleepPeriod = Math.min(sleepPeriod + sleepStep, sleepMaxPeriod);
      }
    }
  }

  render() {
    return (
      <div className="login-redirect">
        <div className="login-redirect-logo">
          <img src="/big-logo.png" alt="plynx" />
          <SimpleLoader />
          <div className="error-text">{this.state.errorText}</div>
        </div>
      </div>
    );
  }
}
