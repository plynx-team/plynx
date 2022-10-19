/* eslint max-classes-per-file: 0 */
import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { PLynxApi } from '../../API';
import { SimpleLoader } from '../LoadingScreen';
import NodeItem from '../Common/NodeItem';
import { utcTimeToLocal } from '../../utils';
import { PluginsProvider } from '../../contexts';
import './MasterState.css';

class ListItem extends Component {
  static propTypes = {
    item: PropTypes.shape({
      runs: PropTypes.array.isRequired,
      host: PropTypes.string.isRequired,
      worker_id: PropTypes.string.isRequired,
      kinds: PropTypes.array.isRequired,
      update_date: PropTypes.string.isRequired,
    }).isRequired,
  };

  render() {
    const isBusy = this.props.item.runs.length > 0;
    return (
     <div className='list-item master-list-item'>
       <div className='host'>{this.props.item.host}</div>
       <div className='worker-id'>{this.props.item.worker_id}</div>
       <div className='kinds'>
        {
            this.props.item.kinds.map(kind => {
              return <div key={kind}> {kind} </div>;
            })
        }
       </div>
       <div className='updated-datetime'>
        {utcTimeToLocal(this.props.item.update_date)}
       </div>
       <div className='running-node'>
        {this.props.item.runs.map(run => (
            <a
                href={`/runs/${run._id}`}
                key={run._id}
                className="node-link"
                style={{"text-decoration": "none"}}

            >
                <NodeItem
                  node={run}
                  key={run._id}
                />
            </a>
        ))}

         {!isBusy &&
           'Idle'
         }
       </div>
     </div>
    );
  }
}

export default class MasterState extends Component {
  constructor(props) {
    super(props);
    this.state = {
      workers: [],
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
      console.log(data);

      this.setState({
        workers: data.items,
        plugins_dict: data.plugins_dict,
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
      await PLynxApi.endpoints.worker_states.getAll({})
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
    const listItems = this.state.workers.map(
          (worker_state) => <ListItem
            item={worker_state}
            key={worker_state.worker_id}
            />);
    return (
      <div className='master-state'>
        <div className='header'>
          Workers
        </div>

        <div className='list'>
          <PluginsProvider value={this.state.plugins_dict}>
              <div className='master-list-item list-header'>
                <div className='host'>Host</div>
                <div className='worker-id'>Worker ID</div>
                <div className='kinds'>Kinds</div>
                <div className='updated-datetime'>Updated</div>
                <div className='running-node'>Nodes</div>
              </div>
              {this.state.loading &&
                <SimpleLoader/>
              }
              {listItems.length ? listItems : <b>No items to show</b>}
          </PluginsProvider>
        </div>
      </div>
    );
  }
}
