import React, { Component } from 'react';
import PropTypes from 'prop-types';
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import cookie from 'react-cookies';
import LoadingScreen from '../LoadingScreen';
import { ALERT_OPTIONS } from '../../constants';

//import "./style.css";

export default class APIObject extends Component {
    constructor(props) {
      super(props);

      this.state = {
        loading: true,
      };

      let token = cookie.load('refresh_token');
      // TODO remove after demo
      if (token === 'Not assigned') {
        token = cookie.load('access_token');
      }
    }

    showAlert(message, type) {
      this.msg.show(message, {
        time: 5000,
        type: 'error',
        icon: <img src={"/alerts/" + type + ".svg"} width="32" height="32" alt={type} />
      });
    }

    sleep(ms) {
      return new Promise(resolve => setTimeout(resolve, ms));
    }

    async componentDidMount() {
      // Loading

      const self = this;
      let loading = true;
      let sleepPeriod = 1000;
      const sleepMaxPeriod = 10000;
      const sleepStep = 1000;

      const loadObject = (response) => {
        if (self.props.onUpdatePlugins) {
          self.props.onUpdatePlugins(response.data.plugins_dict)
        }

        self.props.onUpdateData(response.data);

        loading = false;
      };

      const handleError = (error) => {
        console.error(error);
        console.error('-----------');
        if (!error.response) {
          self.setState({error_message: error});
        } else if (error.response.status === 404) {
          self.props.history.replace("/not_found");
          window.location.reload(false);
          loading = false;
        } else if (error.response.status === 401) {
          PLynxApi.getAccessToken()
          .then((isSuccessfull) => {
            if (!isSuccessfull) {
              console.error("Could not refresh token");
              window.location = '/login';
            } else {
              self.showAlert('Updated access token', 'success');
            }
          });
        }
      };

      /* eslint-disable no-await-in-loop */
      /* eslint-disable no-unmodified-loop-condition */
      while (loading) {
        await PLynxApi.endpoints[self.props.collection].getOne({ id: this.props.object_id})
        .then(loadObject)
        .catch(handleError);
        if (loading) {
          await self.sleep(sleepPeriod);
          sleepPeriod = Math.min(sleepPeriod + sleepStep, sleepMaxPeriod);
        }
      }
      /* eslint-enable no-unmodified-loop-condition */
      /* eslint-enable no-await-in-loop */

      // Stop loading
      self.setState({
        loading: false,
      });
    }

    postData(data, { retryOnAuth = true} = {}) {
      const self = this;
      self.setState({loading: true});

      console.log('Post', data);

      PLynxApi.endpoints[self.props.collection].create(data)
      .then((response) => {
        const data = response.data;
        console.log(data);
        self.setState({loading: false});
        self.props.onPostResponse(data);
      })
      .catch((error) => {
        console.log(error);
        if (error.response.status === 401) {
          PLynxApi.getAccessToken()
          .then((isSuccessfull) => {
            if (!isSuccessfull) {
              console.error("Could not refresh token");
              self.showAlert('Failed to authenticate', 'failed');
            } else if (retryOnAuth) {
                  // Token updated, try posting again
              self.postData(data, {retryOnAuth: false});
            } else {
              self.showAlert(error.response.data.message, 'failed');
            }
          });
        } else {
          try {
            self.showAlert(error.response.data.message, 'failed');
          } catch {
            self.showAlert('Unknown error', 'failed');
          }
        }
        self.setState({loading: false});
      });
    }

    render() {
      return (
          <div
            className={`api-object-view`}
          >
            <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
              {this.state.loading &&
                <LoadingScreen/>
              }
          </div>
      );
    }
}
