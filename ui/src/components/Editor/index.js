/* eslint max-lines: 0 */
import React, { Component } from 'react';
import PropTypes from 'prop-types';
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import cookie from 'react-cookies';
import Controls from './Controls';
import LoadingScreen from '../LoadingScreen';
import {
  ACTION,
  RELOAD_OPTIONS,
  RESPONCE_STATUS,
  ALERT_OPTIONS,
  VALIDATION_CODES,
  GRAPH_RUNNING_STATUS,
} from '../../constants';
import Graph from '../Graph';
import Node from '../Node';
import RunList from '../NodeList/runList';
import "./style.css";


export const VIEW_MODE = Object.freeze({
  NONE: 'NONE',
  GRAPH: 0,
  NODE: 1,
  RUNS: 2,
});


export default class Editor extends Component {
  static propTypes = {
    history: PropTypes.object.isRequired,
    location: PropTypes.object.isRequired,
    match: PropTypes.shape({
      params: PropTypes.shape({
        node_id: PropTypes.string,
      }),
    }),
  }

  constructor(props) {
    super(props);

    this.state = {
      editable: false,
      loading: true,
      view_mode: VIEW_MODE.NONE,
    };

    let token = cookie.load('refresh_token');
    // TODO remove after demo
    if (token === 'Not assigned') {
      token = cookie.load('access_token');
    }

  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async componentDidMount() {
    // Loading

    const self = this;
    let loading = true;
    const node_id = this.props.match.params.node_id.replace(/\$+$/, '');
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    const loadNode = (response) => {
      self.node = response.data.data;
      const executor_info = response.data.plugins_dict.executors_info[self.node.kind];
      const is_graph = executor_info.is_graph;

      const node_running_status = self.node.node_running_status.toUpperCase();

      self.setState({
        node: self.node,
        plugins_dict: response.data.plugins_dict,
        editable: node_running_status === GRAPH_RUNNING_STATUS.CREATED,
        view_mode: is_graph ? VIEW_MODE.GRAPH : VIEW_MODE.NODE,
        is_graph: is_graph,
      });

      console.log('node_id:', node_id);
      if (!node_id.startsWith(self.node._id)) {
        self.props.history.replace("/" + self.props.collection + "/" + self.node._id + '$');
      }

      if (['READY', 'RUNNING', 'FAILED_WAITING'].indexOf(node_running_status) > -1) {
        this.timeout = setTimeout(() => this.checkNodeStatus(), 1000);
      }

      loading = false;
    };

    const handleError = (error) => {
      console.error(error);
      console.error('-----------');
      if (!error.response) {
          self.setState({error_message: error});
      }
      else if (error.response.status === 404) {
        self.props.history.replace("/not_found");
        window.location.reload(false);
        loading = false;
      }
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.showAlert('Failed to authenticate', 'failed');
          } else {
            self.showAlert('Updated access token', 'success');
          }
        });
      }
    };

    /* eslint-disable no-await-in-loop */
    /* eslint-disable no-unmodified-loop-condition */
    while (loading) {
      await PLynxApi.endpoints[self.props.collection].getOne({ id: node_id})
      .then(loadNode)
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

  componentWillUnmount() {
    if (this.timeout) {
      clearTimeout(this.timeout);
    }
  }

  checkNodeStatus() {
    const self = this;
    const node_id = self.node._id;
    PLynxApi.endpoints[self.props.collection].getOne({ id: node_id})
    .then((response) => {
        self.node = response.data.data;

        const node_running_status = self.node.node_running_status.toUpperCase();

        self.setState({
          node: self.node,
          editable: node_running_status === GRAPH_RUNNING_STATUS.CREATED,
        });
        if (self.graph) {
            self.graph.ref.current.updateGraphFromJson(self.node);
        }

        if (['READY', 'RUNNING', 'FAILED_WAITING'].indexOf(node_running_status) > -1) {
          this.timeout = setTimeout(() => this.checkNodeStatus(), 1000);
        }
    })
    .catch((error) => {
      console.log(error);
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (isSuccessfull) {
            self.timeout = setTimeout(() => self.checkNodeStatus(), 1000);
          } else {
            console.error("Could not refresh token");
            self.showAlert('Failed to authenticate', 'failed');
          }
        });
      }
    });
  }

  postNode({node, reloadOption, action}={}) {
    /* action might be in {'save', 'validate', 'approve', 'deprecate'}*/
    const self = this;
    self.setState({loading: true});

    console.log(action, node);

    PLynxApi.endpoints[self.props.collection]
    .create({
      node: node,
      action: action
    })
    .then((response) => {
      const data = response.data;
      console.log(data);
      self.setState({loading: false});
      if (data.status === RESPONCE_STATUS.SUCCESS) {
        if (reloadOption === RELOAD_OPTIONS.RELOAD) {
          window.location.reload();
        }

        if (action === ACTION.SAVE) {
          self.showAlert("Saved", 'success');
        } else if (action === ACTION.VALIDATE) {
          self.showAlert("Valid", 'success');
        } else if (action === ACTION.REARRANGE) {
          self.loadGraphFromJson(data.graph);
        } else if (action === ACTION.UPGRADE_NODES) {
          self.loadGraphFromJson(data.graph);
          let message = "";
          if (data.upgraded_nodes_count > 0) {
            message = "Upgraded " + data.upgraded_nodes_count +
              (data.upgraded_nodes_count > 1 ? " Nodes" : " Node");
          } else {
            message = "No Nodes upgraded";
          }
          self.showAlert(message, 'success');
        } else if (action === ACTION.GENERATE_CODE) {
          self.setState({
            generatedCode: data.code
          });
        } else if (action === ACTION.CREATE_RUN) {
          self.showAlert("Created new run with id: " + response.data.run_id, 'success');
          window.open('/runs/' + response.data.run_id, '_blank');
        } else {
          self.showAlert("Success", 'success');
        }
        if (cookie.load('demoPreview')) {
          cookie.remove('demoPreview', { path: '/' });
        }
      } else if (data.status === RESPONCE_STATUS.VALIDATION_FAILED) {
        console.warn(data.message);
        // TODO smarter traverse
        self.showValidationError(data.validation_error);

        self.showAlert(data.message, 'failed');
      } else {
        console.warn(data.message);
        self.showAlert(data.message, 'failed');
      }
    })
    .catch((error) => {
      console.log(error);
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.showAlert('Failed to authenticate', 'failed');
          } else {
            self.showAlert('Failed to save the graph, please try again', 'failed');
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

  showValidationError(validationError) {
    const children = validationError.children;
    for (let i = 0; i < children.length; ++i) {
      const child = children[i];
      let nodeId = null;
      let node = null;
      switch (child.validation_code) {
        case VALIDATION_CODES.IN_DEPENDENTS:
          this.showValidationError(child);
          break;
        case VALIDATION_CODES.DEPRECATED_NODE:
          nodeId = validationError.object_id;
          node = this.node_lookup[nodeId];

          this.block_lookup[nodeId].highlight = true;
          this.setState({
            "blocks": this.blocks
          });

          this.showAlert("Deprecated Node found: `" + node.title + "`", 'warning');
          break;
        case VALIDATION_CODES.MISSING_INPUT:
          nodeId = validationError.object_id;
          node = this.node_lookup[nodeId];

          this.block_lookup[nodeId].highlight = true;
          this.setState({
            "blocks": this.blocks
          });

          this.showAlert("Missing input `" + child.object_id + "` in node `" + node.title + "`", 'warning');
          break;
        case VALIDATION_CODES.MISSING_PARAMETER:
          this.showAlert("Missing parameter `" + child.object_id + "`", 'warning');
          break;
        default:
      }
    }
  }

  showAlert(message, type) {
    this.msg.show(message, {
      time: 5000,
      type: 'error',
      icon: <img src={"/alerts/" + type + ".svg"} width="32" height="32" alt="alert"/>
    });
  }

  handleNodeChange(node) {
      this.node = node;
  }

  handleSave() {
    this.postNode({
        node: this.node,
        action: ACTION.SAVE,
        reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleValidate() {
    this.postNode({
        node: this.node,
        action: ACTION.VALIDATE,
        reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleApprove() {
    this.postNode({
        node: this.node,
        action: ACTION.CREATE_RUN,
        reloadOption: RELOAD_OPTIONS.NEW_TAB,
    });
  }

  handleRearrange() {
    this.postNode({
        node: this.node,
        action: ACTION.REARRANGE,
        reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleGenerateCode() {
    this.postNode({
        node: this.node,
        action: ACTION.GENERATE_CODE,
        reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleUpgradeNodes() {
    this.postNode({
        node: this.node,
        action: ACTION.UPGRADE_NODES,
        reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleCancel() {
    this.postNode({
        node: this.node,
        action: ACTION.CANCEL,
        reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  render() {
    return (
        <div
          className="editor-view"
        >
          <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
          {this.state.loading &&
            <LoadingScreen
            ></LoadingScreen>
          }
          <Controls className="control-panel"
                    onViewMode={(view_mode) => this.setState({view_mode: view_mode})}
                    readonly={!this.state.editable}
                    graphRunningStatus={this.state.graphRunningStatus}
                    onSave={() => this.handleSave()}
                    onValidate={() => this.handleValidate()}
                    onApprove={() => this.handleApprove()}
                    onRearrange={() => this.handleRearrange()}
                    onGenerateCode={() => this.handleGenerateCode()}
                    onUpgradeNodes={() => this.handleUpgradeNodes()}
                    onClone={() => this.handleClone()}
                    onCancel={() => this.handleCancel()}
                    index={this.state.view_mode}
                    is_graph={this.state.is_graph}
                    key={this.state.view_mode}
          />
          {
              this.state.view_mode === VIEW_MODE.GRAPH &&
              <Graph
                ref={a => this.graph = a}
                node={this.state.node}
                plugins_dict={this.state.plugins_dict}
                onNodeChange={(node) => this.handleNodeChange(node)}
              />
          }
          {
              this.state.view_mode === VIEW_MODE.NODE &&
              <Node
                node={this.state.node}
                plugins_dict={this.state.plugins_dict}
                onNodeChange={(node) => this.handleNodeChange(node)}
              />
          }
          {
              this.state.view_mode === VIEW_MODE.RUNS &&
              <RunList
                showControlls={false}
                search={"original_node:" + this.state.node._id}
              />
          }
          <pre>
          {JSON.stringify(this.state, null, 4)}
          </pre>
        </div>
    );
  }
}
