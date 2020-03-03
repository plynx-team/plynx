import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { PLynxApi } from '../../API';
import {SimpleLoader} from '../LoadingScreen';
import { SPECIAL_USERS } from '../../constants';
import cookie from 'react-cookies';

import './style.css';

export default class LogInRedirect extends Component {
  static propTypes = {
    specialUser: PropTypes.string.isRequired,
  }

  constructor(props) {
    super(props);
    document.title = "PLynx";

    this.state = {
      errorText: "",
    };
  }

  componentDidMount() {
    this.loginUser(this.props.specialUser);
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async loginUser(specialUser) {
    // Loading

    const self = this;
    let loading = true;
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;
    let maxTry = 3;

    self.setState({
      loading: true,
    });

    let handleResponse = null;
    let promise = null;

    if (specialUser === SPECIAL_USERS.DEMO) {
      promise = PLynxApi.endpoints.demo.getCustom({
        method: 'post'
      });
      handleResponse = response => {
        cookie.save('access_token', response.data.access_token, { path: '/' });
        cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
        cookie.save('username', response.data.username, { path: '/' });
        cookie.save('showTour', true, { path: '/' });
        window.location = response.data.url;
        loading = false;
      };
    } else if (specialUser === SPECIAL_USERS.DEFAULT) {
      promise = PLynxApi.endpoints.token.getCustom({
        method: 'get',
        auth:
        {
          username: SPECIAL_USERS.DEFAULT,
          password: ''
        }
      });
      handleResponse = response => {
        cookie.save('access_token', response.data.access_token, { path: '/' });
        cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
        cookie.save('username', SPECIAL_USERS.DEFAULT, { path: '/' });
        window.location = '/workflows';
      };
    }

    const errorHandler = (error) => {
      --maxTry;
      if (maxTry < 0) {
        window.location = '/login';
      }
      this.setState({errorText: error.message});
    };

    /* eslint-disable no-await-in-loop */
    /* eslint-disable no-unmodified-loop-condition */
    while (loading) {
      await promise
      .then(handleResponse)
      .catch(errorHandler);
      if (loading) {
        await self.sleep(sleepPeriod);
        sleepPeriod = Math.min(sleepPeriod + sleepStep, sleepMaxPeriod);
      }
    }
    /* eslint-enable no-unmodified-loop-condition */
    /* eslint-enable no-await-in-loop */
  }

  handleDemo() {
    console.log("Demo");
    this.loginUser(SPECIAL_USERS.DEMO);
  }

  render() {
    return (
      <div className='login-redirect'>
        <div className="login-redirect-logo">
            <img
                src="/big-logo.png"
                alt="plynx"
            />
            <SimpleLoader />
            <div className="error-text">
                {this.state.errorText}
            </div>
        </div>
      </div>
    );
  }
}
