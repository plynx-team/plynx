// src/components/NotFound/index.js
import React, { Component } from 'react';
import { PlynxApi } from '../../API.js';
import LoadingScreen from '../LoadingScreen.js'
import { SPECIAL_USERS } from '../../constants.js';
import cookie from 'react-cookies'

import './style.css';

export default class Welcome extends Component {
  constructor(props) {
    super(props);
    document.title = "Plynx";

    this.state = {
      loading: false
    };
  }

  componentDidMount() {
    this.loginUser(SPECIAL_USERS.DEFAULT);
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async loginUser(specialUser) {
    // Loading

    var self = this;
    var loading = true;
    var sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    self.setState({
      loading: true,
    });

    var handleResponse = null;
    var promise = null;

    if (specialUser === SPECIAL_USERS.DEMO) {
      promise = PlynxApi.endpoints.demo.getCustom({
          method: 'post'
        });
      handleResponse = response => {
        cookie.save('access_token', response.data.access_token, { path: '/' });
        cookie.save('refresh_token', response.data.refresh_token, { path: '/' });
        cookie.save('username', response.data.username, { path: '/' });
        cookie.save('demoPreview', true, { path: '/' });
        window.location = '/graphs';
        loading = false;
      };
    } else if (specialUser === SPECIAL_USERS.DEFAULT) {
      promise = PlynxApi.endpoints.token.getCustom({
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
        //dispatch({ type: AUTH_USER });
        //window.location.href = CLIENT_ROOT_URL + '/dashboard';
        window.location = '/graphs';
      };
    }

    var errorHandler = (error) => {
      if (specialUser === SPECIAL_USERS.DEFAULT) {
        loading = false;
      }
      //errorHandler(dispatch, error.response, AUTH_ERROR)
    };

    while (loading) {
      await promise
      .then(handleResponse)
      .catch(errorHandler);
      if (loading) {
        await self.sleep(sleepPeriod);
        sleepPeriod = Math.min(sleepPeriod + sleepStep, sleepMaxPeriod);
      }
    }

    // Stop loading
    self.setState({
      loading: false,
    });
  }

  handleDemo() {
    console.log("Demo");
    this.loginUser(SPECIAL_USERS.DEMO);
  }

  render() {
    return (
      <div className='Welcome'>
        {this.state.loading &&
          <LoadingScreen />
        }
        <div className='WelcomeBlock'>
          <img className="img"
               src='01_flexible.png'
               width="100%"
               alt="background" />
          <div className="Demo">
            {!cookie.load('username') &&
              <div className="DemoButton" onClick={() => this.handleDemo()}>
                Try Live Demo
              </div>
            }
          </div>
        </div>
      </div>
    );
  }
}
