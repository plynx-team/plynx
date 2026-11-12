import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import { SimpleLoader } from '../LoadingScreen';
import NodeItem from '../Common/NodeItem';
import { utcTimeToLocal } from '../../utils';
import { PluginsProvider } from '../../contexts';
import { NodeData, PluginsDict } from '../../types';
import './MasterState.css';

export interface WorkerStateItem {
  runs: NodeData[];
  host: string;
  worker_id: string;
  kinds: string[];
  update_date: string;
}

interface ListItemProps {
  item: WorkerStateItem;
}

class ListItem extends Component<ListItemProps> {
  render() {
    const isBusy = this.props.item.runs.length > 0;
    return (
      <div className="list-item master-list-item">
        <div className="host">{this.props.item.host}</div>
        <div className="worker-id">{this.props.item.worker_id}</div>
        <div className="kinds">
          {this.props.item.kinds.map((kind) => (
            <div key={kind}> {kind} </div>
          ))}
        </div>
        <div className="updated-datetime">
          {utcTimeToLocal(this.props.item.update_date)}
        </div>
        <div className="running-node">
          {this.props.item.runs.map((run) => (
            <a
              href={`/runs/${run._id}`}
              key={run._id}
              className="node-link"
              style={{ textDecoration: 'none' }}
            >
              <NodeItem node={run} key={run._id} />
            </a>
          ))}

          {!isBusy && 'Idle'}
        </div>
      </div>
    );
  }
}

export interface MasterStateProps {
  history?: any;
}

interface MasterStateState {
  workers: WorkerStateItem[];
  loading: boolean;
  plugins_dict?: PluginsDict;
}

export default class MasterState extends Component<MasterStateProps, MasterStateState> {
  mounted: boolean = false;

  constructor(props: MasterStateProps) {
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
    let loading = true;
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    if (this.mounted) {
      this.setState({
        loading: true,
      });
    }

    const handleResponse = (response: any) => {
      const data = response.data;
      this.setState({
        workers: data.items || [],
        plugins_dict: data.plugins_dict,
      });
      loading = false;
    };

    const handleError = (error: any) => {
      if (error.response && error.response.status === 401) {
        PLynxApi.getAccessToken().then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error('Could not refresh token');
            if (this.props.history) {
              this.props.history.push('/login/');
            } else {
              window.location.href = '/login';
            }
          }
        });
      } else {
        throw error;
      }
    };

    while (loading) {
      await PLynxApi.endpoints.worker_states
        .getAll({})
        .then(handleResponse)
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

  sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  render() {
    const listItems = this.state.workers.map((worker_state) => (
      <ListItem item={worker_state} key={worker_state.worker_id} />
    ));

    return (
      <div className="master-state">
        <div className="header">Workers</div>

        <div className="list">
          <PluginsProvider
            value={this.state.plugins_dict || { resources_dict: {}, executors_info: {} }}
          >
            <div className="master-list-item list-header">
              <div className="host">Host</div>
              <div className="worker-id">Worker ID</div>
              <div className="kinds">Kinds</div>
              <div className="updated-datetime">Updated</div>
              <div className="running-node">Nodes</div>
            </div>
            {this.state.loading && <SimpleLoader />}
            {listItems.length ? listItems : <b>No items to show</b>}
          </PluginsProvider>
        </div>
      </div>
    );
  }
}
