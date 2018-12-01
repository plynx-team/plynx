// src/components/About/index.js
import React, { Component } from 'react';
import { PlynxApi } from '../../API';
import { SimpleLoader } from '../LoadingScreen'
import GraphList from '../GraphList/GraphList'
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

    var self = this;
    var loading = true;
    var sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    if (this.mounted) {
      self.setState({
        loading: true,
      });
    }

    var handleResponse = function (response) {
      let data = response.data;
      console.log(data.graphs);
      self.setState(
        {
          graphs: data.graphs,
        });
      loading = false;
    };

    var handleError = function (error) {
      if (error.response && error.response.status === 401) {
        PlynxApi.getAccessToken()
        .then(function (isSuccessfull) {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.props.history.push("/login/");
          }
        });
      } else {
        throw error;
      }
    };

    while (loading) {
      await PlynxApi.endpoints.graphs.getAll( {
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
