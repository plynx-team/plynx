import React, { Component, ReactNode } from 'react';
// @ts-ignore
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../api';
import cookie from '../../cookie';
import LoadingScreen from '../LoadingScreen';
import { ALERT_OPTIONS } from '../../constants';

export interface APIObjectProps {
  object_id: string;
  collection: string;
  onUpdatePlugins?: (plugins: any) => void;
  onUpdateData: (data: any) => void;
  onPostResponse: (data: any) => void;
  history?: any;
}

interface APIObjectState {
  loading: boolean;
  error_message?: any;
}

export default class APIObject extends Component<APIObjectProps, APIObjectState> {
  msg: any;

  constructor(props: APIObjectProps) {
    super(props);

    this.state = {
      loading: true,
    };

    let token = cookie.load('refresh_token');
    if (token === 'Not assigned') {
      token = cookie.load('access_token');
    }
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

  sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async componentDidMount() {
    let loading = true;
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    const loadObject = (response: any) => {
      if (this.props.onUpdatePlugins) {
        this.props.onUpdatePlugins(response.data.plugins_dict);
      }

      this.props.onUpdateData(response.data);
      loading = false;
    };

    const handleError = (error: any) => {
      console.error(error);
      if (!error.response) {
        this.setState({ error_message: error });
      } else if (error.response.status === 404) {
        if (this.props.history) {
          this.props.history.replace('/not_found');
        } else {
          window.location.href = '/not_found';
        }
        loading = false;
      } else if (error.response.status === 401) {
        PLynxApi.getAccessToken().then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error('Could not refresh token');
            window.location.href = '/login';
          } else {
            this.showAlert('Updated access token', 'success');
          }
        });
      }
    };

    while (loading) {
      await PLynxApi.endpoints[this.props.collection]
        .getOne({ id: this.props.object_id })
        .then(loadObject)
        .catch(handleError);
      if (loading) {
        await this.sleep(sleepPeriod);
        sleepPeriod = Math.min(sleepPeriod + sleepStep, sleepMaxPeriod);
      }
    }

    this.setState({
      loading: false,
    });
  }

  postData(data: any, { retryOnAuth = true } = {}) {
    this.setState({ loading: true });

    PLynxApi.endpoints[this.props.collection]
      .create(data)
      .then((response: any) => {
        this.setState({ loading: false });
        this.props.onPostResponse(response.data);
      })
      .catch((error: any) => {
        console.error(error);
        if (error.response && error.response.status === 401) {
          PLynxApi.getAccessToken().then((isSuccessfull) => {
            if (!isSuccessfull) {
              console.error('Could not refresh token');
              this.showAlert('Failed to authenticate', 'failed');
            } else if (retryOnAuth) {
              this.postData(data, { retryOnAuth: false });
            } else {
              this.showAlert(error.response.data.message, 'failed');
            }
          });
        } else {
          try {
            this.showAlert(error.response.data.message, 'failed');
          } catch {
            this.showAlert('Unknown error', 'failed');
          }
        }
        this.setState({ loading: false });
      });
  }

  render(): ReactNode {
    return (
      <div className="api-object-view">
        <AlertContainer ref={(a: any) => (this.msg = a)} {...ALERT_OPTIONS} />
        {this.state.loading && <LoadingScreen />}
      </div>
    );
  }
}
