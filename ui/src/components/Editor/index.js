import React, { Component } from 'react';
import PropTypes from 'prop-types';
import queryString from 'query-string'
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import cookie from 'react-cookies';
import LoadingScreen from '../LoadingScreen';
import {
  ACTION,
  RELOAD_OPTIONS,
  RESPONCE_STATUS,
  ALERT_OPTIONS,
  VALIDATION_CODES,
  VALIDATION_TARGET_TYPE,
  NODE_STATUS,
  COLLECTIONS,
  ACTIVE_NODE_RUNNING_STATUSES,
} from '../../constants';
import Graph from '../Graph';
import Node from '../Node';
import RunList from '../nodeList/runList';
import DeprecateDialog from '../Dialogs/DeprecateDialog';
import TextViewDialog from '../Dialogs/TextViewDialog';
import { makeControlPanel, makeControlToggles, makeControlButton, makeControlSeparator } from '../Common/controlButton';
import "./style.css";


export const VIEW_MODE = Object.freeze({
  NONE: 'none',
  GRAPH: 0,
  NODE: 1,
  RUNS: 2,
});


const FIRST_TIME_APPROVED_STATE = 'first_time_approved_state';

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
      deprecateQuestionDialog: false,
      deprecateParentDialog: false,
      collection: null,
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

  updateNode(node, force) {
      this.node = node;
      document.title = this.node.title + " - PLynx";

      this.setState({
        node: this.node,
        editable: this.props.collection === COLLECTIONS.TEMPLATES && this.node.node_status.toUpperCase() === NODE_STATUS.CREATED,
        collection: this.props.collection,
      });
      if (this.graphComponent) {
          if (force) {
              this.graphComponent.ref.current.loadGraphFromJson(this.node);
          } else {
              this.graphComponent.ref.current.updateGraphFromJson(this.node);
          }
      }
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
      const searchValues = queryString.parse(this.props.location.search)
      var node = response.data.node;

      if (searchValues.sub_node_id) {
          let sub_nodes = null;
          if (!Array.isArray(searchValues.sub_node_id))
          {
              const sub_node_id = searchValues.sub_node_id = [searchValues.sub_node_id]
          }
          for (let sub_node_id of searchValues.sub_node_id) {
              sub_node_id = sub_node_id.replace(/^\$+|\$+$/g, '');
              for (let i = 0; i < node.parameters.length; ++i) {
                  if (node.parameters[i].name === '_nodes') {
                      sub_nodes = node.parameters[i].value.value;
                      break;
                  }
              }
              for (const sub_node of sub_nodes) {
                  if (sub_node._id === sub_node_id) {
                      node = sub_node;
                      break;
                  }
              }
          }
      }

      self.updateNode(node, true);

      const executor_info = response.data.plugins_dict.executors_info[self.node.kind];
      console.log('plugins_dict', response.data.plugins_dict);
      const is_graph = executor_info.is_graph;

      var view_mode = is_graph ? VIEW_MODE.GRAPH : VIEW_MODE.NODE;
      if ('view_mode' in searchValues) {
          view_mode = Math.max(parseInt(searchValues['view_mode']), is_graph ? 0 : 1);
      }

      self.setState({
        plugins_dict: response.data.plugins_dict,
        view_mode: view_mode,
        is_graph: is_graph,
        is_workflow: response.data.plugins_dict.workflows_dict.hasOwnProperty(node.kind),
      });

      console.log('node_id:', node_id);
      if (!node_id.startsWith(self.node._id) && !searchValues.sub_node_id) {
        self.props.history.replace("/" + self.props.collection + "/" + self.node._id + '$');
      }

      self.initializeUpdate();

      const first_time_approved_node_id = window.sessionStorage.getItem(FIRST_TIME_APPROVED_STATE);
      if (first_time_approved_node_id === self.node._id) {
        this.setState({deprecateParentDialog: true});
      }
      if (first_time_approved_node_id) {
        window.sessionStorage.removeItem('first_time_approved_state');
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
        self.updateNode(response.data.node, false)

        self.initializeUpdate();
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

  initializeUpdate() {
      const node_running_status = this.node.node_running_status.toUpperCase();
      if (this.props.collection === COLLECTIONS.RUNS && ACTIVE_NODE_RUNNING_STATUSES.has(node_running_status)) {
        this.timeout = setTimeout(() => this.checkNodeStatus(), 1000);
      }
  }

  postNode({node, reloadOption, action, retryOnAuth = true}={}) {
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
          if (action === ACTION.APPROVE && node.parent_node_id) {
            window.sessionStorage.setItem(FIRST_TIME_APPROVED_STATE, node._id);
          }
          window.location.reload();
        } else if (reloadOption === RELOAD_OPTIONS.OPEN_NEW_LINK) {
          this.props.history.push(response.data.url);
        }

        if (action === ACTION.SAVE) {
          self.showAlert("Saved", 'success');
        } else if (action === ACTION.VALIDATE) {
          self.showAlert("Valid", 'success');
        } if (action === ACTION.PREVIEW_CMD) {
          self.setState({preview_text: data.preview_text});
        } else if (action === ACTION.REARRANGE_NODES) {
          self.updateNode(data.node, true)
        } else if (action === ACTION.UPGRADE_NODES) {
          self.updateNode(data.node, true)
          console.log('new', data.node);
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
          window.open(`/${COLLECTIONS.RUNS}/${response.data.run_id}`, '_blank');
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
            if (retryOnAuth) {
                // Token updated, try posting again
                self.postNode({node:node, reloadOption:reloadOption, action:action, retryOnAuth:false})
            } else {
                self.showAlert('Failed to save the graph, please try again', 'failed');
            }
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
    if (validationError.target === VALIDATION_TARGET_TYPE.GRAPH) {
        if (this.graphComponent) {
            this.graphComponent.ref.current.showValidationError(validationError);
        } else {
            this.showAlert('Errors in the graph structure', 'failed');
        }
        return;
    }

    const children = validationError.children;
    for (let i = 0; i < children.length; ++i) {
      const child = children[i];
      let nodeId = null;
      let node = null;
      console.log('?', child);
      switch (child.validation_code) {
        case VALIDATION_CODES.IN_DEPENDENTS:
          this.showValidationError(child);
          break;
        case VALIDATION_CODES.MISSING_PARAMETER:
          this.showAlert("Missing parameter `" + child.object_id + "`", 'warning');
          break;
        case VALIDATION_CODES.MINIMUM_COUNT_MUST_NOT_BE_NEGATIVE:
          this.showAlert(`Minimum count of inputs cannot be negative. Input: '${child.object_id}'`, 'warning');
          break;
        case VALIDATION_CODES.MAXIMUM_COUNT_MUST_BE_GREATER_THAN_MINIMUM:
          this.showAlert(`Minimum number of inputs is greater than maximum. Input: '${child.object_id}'`, 'warning');
          break;
        case VALIDATION_CODES.MAXIMUM_COUNT_MUST_NOT_BE_ZERO:
          this.showAlert(`Maximum number of inputs cannot be 0. Input: '${child.object_id}'`, 'warning');
          break;
        default:
          this.showAlert(`${child.validation_code}. Input: '${child.object_id}'`, 'warning');
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
    console.log('to_save', this.node);
    this.postNode({
        node: this.node,
        action: ACTION.SAVE,
        reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handlePreview() {
      this.postNode({
          node: this.node,
          action: ACTION.PREVIEW_CMD,
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

  handleRun() {
    this.postNode({
        node: this.node,
        action: ACTION.CREATE_RUN,
        reloadOption: RELOAD_OPTIONS.NEW_TAB,
    });
  }

  handleApprove() {
    this.postNode({
        node: this.node,
        action: ACTION.APPROVE,
        reloadOption: RELOAD_OPTIONS.RELOAD,
    });
  }

  handleRearrange() {
    this.postNode({
        node: this.node,
        action: ACTION.REARRANGE_NODES,
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

  handleClone() {
    this.postNode({
        node: this.node,
        action: ACTION.CLONE,
        reloadOption: RELOAD_OPTIONS.OPEN_NEW_LINK,
    });
  }

  handleDeprecateClick() {
    this.setState({deprecateQuestionDialog: true});
  }

  handleDeprecate(node, action) {
    this.postNode({
        node: node,
        action: action,
        reloadOption: RELOAD_OPTIONS.RELOAD,
    });
  }

  handleCloseDeprecateDialog() {
    this.setState({
      deprecateQuestionDialog: false,
      deprecateParentDialog: false
    });
  }

  handleSetViewMode(view_mode) {
    this.setState({view_mode: view_mode});
    const searchValues = queryString.parse(this.props.location.search);
    searchValues.view_mode = view_mode;

    this.props.history.push({
        search: '?' + queryString.stringify(searchValues)
    })

  }

  makeControls() {
      let items = [
          {
              render: makeControlToggles,
              props: {
                  items: [
                      {
                        img: 'grid.svg',
                        text: 'Graph',
                        value: VIEW_MODE.GRAPH,
                        enabled: this.state.is_graph,
                    },
                    {
                      img: 'sliders.svg',
                      text: 'Properties',
                      value: VIEW_MODE.NODE,
                    },
                    {
                      img: 'list.svg',
                      text: 'Runs',
                      value: VIEW_MODE.RUNS,
                    },
                  ],
                index: this.state.view_mode,
                onIndexChange: (view_mode) => this.handleSetViewMode(view_mode),
                key: 'key' + this.state.view_mode,
              }
          },

          {
              render: makeControlSeparator,
              props: {key: 'separator_1'}
          },

          {
              render: makeControlButton,
              props: {
                img: 'save.svg',
                text: 'Save',
                enabled: this.state.editable,
                func: () => this.handleSave(),
              },
          }, {
              render: makeControlButton,
              props: {
                img: 'check-square.svg',
                text: 'Validate',
                enabled: this.state.editable,
                func: () => this.handleValidate(),
              },
          }, {
              render: makeControlButton,
              props: {
                img: 'play.svg',
                text: 'Run',
                enabled: this.state.is_workflow && this.state.collection === COLLECTIONS.TEMPLATES,
                func: () => this.handleRun(),
              },
          }, {
              render: makeControlButton,
              props: {
                img: 'check.svg',
                text: 'Approve',
                enabled: !this.state.is_workflow && this.state.editable,
                func: () => this.handleApprove(),
              },
          }, {
              render: makeControlButton,
              props: {
                img: 'x.svg',
                text: 'Deprecate',
                enabled: !this.state.is_workflow && !this.state.editable,
                func: () => this.handleDeprecateClick(),
              },
          }, {
              render: makeControlButton,
              props: {
                img: 'copy.svg',
                text: 'Clone',
                func: () => this.handleClone(),
              },
          },

          {
              render: makeControlSeparator,
              props: {key: 'separator_2'}
          },

          {
              render: makeControlButton,
              props: {
                img: 'trending-up.svg',
                text: 'Upgrade Nodes',
                enabled: this.state.is_graph && this.state.editable,
                func: () => this.handleUpgradeNodes(),
              },
          }, {
              render: makeControlButton,
              props: {
                img: 'rearrange.svg',
                text: 'Rearrange nodes',
                enabled: this.state.is_graph,
                func: () => this.handleRearrange(),
              },
          }, {
              render: makeControlButton,
              props: {
                img: 'preview.svg',
                text: 'API',
                enabled: this.state.is_graph,
                func: () => this.handleGenerateCode(),
              }
          }, {
              render: makeControlButton,
              props: {
                img: 'preview.svg',
                text: 'Preview',
                enabled: !this.state.is_graph,
                func: () => this.handlePreview(),
              },
          },
      ];

      return makeControlPanel(
          {
              props: {
                  items: items,
                  key: this.state.view_mode + this.state.editable,
              },
      });
  }

  render() {
    let node_running_status = this.state.node ? this.state.node.node_running_status.toLowerCase(): "";
    return (
        <div
          className={`editor-view node-running-status-${node_running_status}`}
        >
          <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
          {this.state.loading &&
            <LoadingScreen
            ></LoadingScreen>
          }
          {
            this.state.deprecateQuestionDialog &&
            <DeprecateDialog
              onClose={() => this.handleCloseDeprecateDialog()}
              prev_node_id={this.state.node._id}
              onDeprecate={(node_, action) => this.handleDeprecate(node_, action)}
              title={"Would you like to deprecate this Operation?"}
              />
          }
          {
            this.state.deprecateParentDialog &&
            <DeprecateDialog
              onClose={() => this.handleCloseDeprecateDialog()}
              prev_node_id={this.state.node.parent_node_id}
              new_node_id={this.state.node._id}
              onDeprecate={(node_, action) => this.handleDeprecate(node_, action)}
              title={"Would you like to deprecate parent Operation?"}
              />
          }
          {
            this.state.preview_text &&
            <TextViewDialog className="TextViewDialog"
              title='Preview'
              text={this.state.preview_text}
              onClose={() => this.setState({preview_text: null})}
            />
          }
          {this.makeControls()}
          <div className="editor-content">
              {
                  this.state.view_mode === VIEW_MODE.GRAPH &&
                  <Graph
                    ref={a => this.graphComponent = a}
                    node={this.state.node}
                    plugins_dict={this.state.plugins_dict}
                    onNodeChange={(node) => this.handleNodeChange(node)}
                    editable={this.state.editable}
                    showAlert={(message, type) => this.showAlert(message, type)}
                  />
              }
              {
                  this.state.view_mode === VIEW_MODE.NODE &&
                  <Node
                    ref={a => this.nodeComponent = a}
                    node={this.state.node}
                    plugins_dict={this.state.plugins_dict}
                    is_workflow={this.state.is_workflow}
                    is_graph={this.state.is_graph}
                    onNodeChange={(node) => this.handleNodeChange(node)}
                  />
              }
              {
                  this.state.view_mode === VIEW_MODE.RUNS &&
                  <RunList
                    showControlls={false}
                    search={"original_node_id:" + this.state.node._id}
                  />
              }
          </div>
        </div>
    );
  }
}
