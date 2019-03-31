import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import { SimpleLoader } from '../LoadingScreen';
import GraphList from '../GraphList/GraphList';
import '../Common/List.css';
import './Graphs.css';

export default class Graphs extends Component {
  constructor(props) {
    super(props);
    this.state = {
      graphs: [],
      loading: true,
    };

    this.loadState();
  }

  componentDidMount() {
    this.mounted = true;
  }

  componentWillUnmount() {
    this.mounted = false;
  }

  async loadState() {
    // Loading

    const self = this;
    let loading = true;
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    if (this.mounted) {
      self.setState({
        loading: true,
      });
    }

    const handleResponse = (response) => {
      const data = response.data;
      console.log(data.graphs);
      self.setState(
        {
          graphs: data.graphs,
        });
      loading = false;
    };

    const handleError = (error) => {
      if (error.response && error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.props.history.push("/login/");
          }
        });
      } else {
        throw error;
      }
    };

    /* eslint-disable no-await-in-loop */
    /* eslint-disable no-unmodified-loop-condition */
    while (loading) {
      await PLynxApi.endpoints.graphs.getAll({
        query: {
          offset: 0,
          per_page: 10,
          search: '',
          recent: true,
        }
      })
      .then(handleResponse)
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

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  render() {
    return (
      <div className='graphs-state'>
        <div className='header'>
          Recent Graphs
        </div>

        {this.state.loading &&
          <SimpleLoader/>
        }
        <GraphList graphs={this.state.graphs}
          />
      </div>
    );
  }
}
