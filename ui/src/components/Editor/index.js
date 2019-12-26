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
  RESPONCE_STATUS,
  ALERT_OPTIONS,
  VALIDATION_CODES,
  GRAPH_RUNNING_STATUS,
} from '../../constants';
import Graph from '../Graph';
import Node from '../Node';
import "./style.css";


export const VIEW_MODE = Object.freeze({
  NONE: 'NONE',
  GRAPH: 'GRAPH',
  NODE: 'NODE',
  RUNS: 'RUNS',
});


export default class Editor extends Component {
  static propTypes = {
    history: PropTypes.object.isRequired,
    location: PropTypes.object.isRequired,
    match: PropTypes.shape({
      params: PropTypes.shape({
        graph_id: PropTypes.string,
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
    const graph_id = this.props.match.params.node_id.replace(/\$+$/, '');
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    const loadNode = (response) => {
      self.node = response.data.data;
      self.setState({
        node: self.node,
        plugins_dict: response.data.plugins_dict,
        editable: self.node.node_running_status.toUpperCase() === GRAPH_RUNNING_STATUS.CREATED,
        view_mode: VIEW_MODE.GRAPH,
      });

      console.log(graph_id);
      if (graph_id === 'new') {
        self.props.history.replace("/graphs/" + self.graph._id);
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
      await PLynxApi.endpoints.nodes.getOne({ id: graph_id})
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

  postGraph(node, reloadOnSuccess, action) {
    /* action might be in {'save', 'validate', 'approve', 'deprecate'}*/
    const self = this;
    self.setState({loading: true});
    PLynxApi.endpoints.nodes
    .create({
      node: node,
      action: action
    })
    .then((response) => {
      const data = response.data;
      console.log(data);
      self.setState({loading: false});
      if (data.status === RESPONCE_STATUS.SUCCESS) {
        if (reloadOnSuccess) {
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
    console.log(this.node);
    this.postGraph(this.node, false, ACTION.SAVE);
  }

  handleValidate() {
    console.log(this.node);
    this.postGraph(this.node, false, ACTION.VALIDATE);
  }

  handleApprove() {
    console.log(this.node);
    this.postGraph(this.node, true, ACTION.APPROVE);
  }

  handleRearrange() {
    this.postGraph(this.node, false, ACTION.REARRANGE);
  }

  handleGenerateCode() {
    this.postGraph(this.node, false, ACTION.GENERATE_CODE);
  }

  handleUpgradeNodes() {
    this.postGraph(this.node, false, ACTION.UPGRADE_NODES);
  }

  handleCancel() {
    this.postGraph(this.node, false, ACTION.CANCEL);
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
          <Controls className="ControlButtons"
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
          />
          {
              this.state.view_mode === VIEW_MODE.GRAPH &&
              <Graph
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
          <pre>
          {JSON.stringify(this.state, null, 4)}
          </pre>
        </div>
    );
  }
}
