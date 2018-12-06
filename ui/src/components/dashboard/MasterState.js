// src/components/About/index.js
import React, { Component } from 'react';
import { PlynxApi } from '../../API.js';
import { SimpleLoader } from '../LoadingScreen.js'
import NodeItem from '../Common/NodeItem.js'
import '../Common/List.css';
import './MasterState.css';

class ListItem extends Component {
  render() {
    var isBusy = Boolean(this.props.worker_state.node);
    return (
      <a className='list-item master-list-item' href={
        isBusy ?
        '/graphs/' + this.props.worker_state.graph_id + '?nid=' + this.props.worker_state.node._id:
        '#'}>
        <div className='host'>{this.props.worker_state.host}</div>
        <div className='worker-id'>{this.props.worker_state.worker_id}</div>
        <div className='graph'>
          {isBusy &&
            this.props.worker_state.graph_id
          }
          {!isBusy &&
            'None'
          }
        </div>
        <div className='running-node'>
          {isBusy &&
            <NodeItem
              node={this.props.worker_state.node}
            />
          }
          {!isBusy &&
            'Idle'
          }
        </div>
      </a>
    );
  }
};

export default class MasterState extends Component {
  constructor(props) {
    super(props);
    this.state = {
      master_state: {
        'workers': [],
        'update_date': '-',
      },
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
      var data = response.data;
      console.log(data);

      // Do not change state if master_state is null (not found)
      if (data.master_state) {
        // Format date
        var date = new Date(data.master_state.update_date + 'Z');  // Make date it UTC
        data.master_state.update_date = date.toString();

        self.setState(
          {
            master_state: data.master_state,
          });
      }
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
      await PlynxApi.endpoints.master_state.getAll( {
        query: {
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
    const listItems = this.state.master_state.workers.map(
          (worker_state) => <ListItem
            worker_state={worker_state}
            key={worker_state.worker_id}
            />);
    return (
      <div className='master-state'>
        <div className='header'>
          Workers
        </div>

        <div className='list'>
          <div className='master-list-item list-header'>
            <div className='host'>Host</div>
            <div className='worker-id'>Worker ID</div>
            <div className='graph'>Graph ID</div>
            <div className='running-node'>Node</div>
          </div>
          {this.state.loading &&
            <SimpleLoader/>
          }
          {listItems.length ? listItems : <b>No items to show</b>}
        </div>
        <div className='updated'>
          Updated: {this.state.master_state.update_date}
        </div>
      </div>
    );
  }
}
