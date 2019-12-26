import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { PLynxApi } from '../../API';
import NodeProperties from './NodeProperties';
import ControlButtons from './ControlButtons';
import InOutList from './InOutList';
import ParameterList from './ParameterList';
import DeprecateDialog from '../Dialogs/DeprecateDialog';
import TextViewDialog from '../Dialogs/TextViewDialog';
import {PluginsProvider, PluginsConsumer} from '../../contexts';
import { ObjectID } from 'bson';
import {HotKeys} from 'react-hotkeys';
import { ACTION, RESPONCE_STATUS, NODE_RUNNING_STATUS, KEY_MAP } from '../../constants';

import './style.css';


export default class Node extends Component {
  constructor(props) {
    super(props);
    document.title = "Node";

    this.state = {
      loading: true,
      readOnly: true,
      deprecateQuestionDialog: false,
      deprecateParentDialog: false,
    };
  }

  keyHandlers = {
    escPressed: () => {
      this.closeAllDialogs();
    },
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async componentDidMount() {
      console.log('componentDidMount');
    this.loadNodeFromJson(this.props.node)
  }

  loadNodeFromJson(data) {
    console.log("loadNodeFromJson", data);
    this.node = data;
    this.setState({node: this.node});
    document.title = data.title + " - Node - PLynx";
    const node_status = data.node_status;
    this.setState({readOnly: node_status !== NODE_RUNNING_STATUS.CREATED});

    const first_time_approved_node_id = window.sessionStorage.getItem('first_time_approved_state');
    if (first_time_approved_node_id === data._id) {
      this.setState({deprecateParentDialog: true});
    }
    if (first_time_approved_node_id) {
      window.sessionStorage.removeItem('first_time_approved_state');
    }
  }

  handleParameterChanged(name, value) {
      /*
    const node = this.state.node;
    node[name] = value;
    this.setState(node);
*/
    this.node[name] = value;
    this.setState({node: this.node});
    this.props.onNodeChange(this.node);
  }

  handleSave() {
    console.log(this.state.node);
    this.postNode(this.state.node, false, ACTION.SAVE);
  }

  handlePreview() {
    console.log(this.state.node);
    this.postNode(this.state.node, false, ACTION.PREVIEW_CMD);
  }

  handleSaveApprove() {
    this.postNode(this.state.node, true, ACTION.APPROVE);
  }

  handleClone() {
    const node = this.state.node;
    node.node_status = NODE_RUNNING_STATUS.CREATED;
    node.parent_node = node._id;
    if (node.successor_node) {
      delete node.successor_node;
    }
    node._id = new ObjectID().toString();

    this.loadNodeFromJson(node);
    this.props.history.push("/nodes/" + node._id + '$');
  }

  handleSuccessApprove() {
    const node = this.state.node;
    if (node && node.parent_node) {
      this.setState({deprecateQuestionDialog: true});
    }
  }

  handleCloseDeprecateDialog() {
    this.setState({
      deprecateQuestionDialog: false,
      deprecateParentDialog: false
    });
  }

  handleClosePreview() {
    this.setState({preview_text: null});
  }

  closeAllDialogs() {
    this.handleCloseDeprecateDialog();
    this.handleClosePreview();
  }

  handleDeprecateClick() {
    this.setState({deprecateQuestionDialog: true});
  }

  handleDeprecate(node, action) {
    this.postNode(node, true, action);
  }

  postNode(node, reloadOnSuccess, action, successCallback = null) {
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
        if (successCallback) {
          successCallback();
        }
        if (reloadOnSuccess) {
          if (action === ACTION.APPROVE && node.parent_node) {
            window.sessionStorage.setItem('first_time_approved_state', node._id);
          }
          window.location.reload();
        }
        if (action === ACTION.PREVIEW_CMD) {
          self.setState({preview_text: data.preview_text});
        } else if (action === ACTION.SAVE) {
          self.showAlert("Saved", 'success');
        }
      } else if (data.status === RESPONCE_STATUS.VALIDATION_FAILED) {
        console.warn(data.message);
        // TODO smarter traverse
        const validationErrors = data.validation_error.children;
        for (let i = 0; i < validationErrors.length; ++i) {
          const validationError = validationErrors[i];
          self.showAlert(validationError.validation_code + ': ' + validationError.object_id, 'warning');
        }

        self.showAlert(data.message, 'failed');
      } else {
        console.warn(data.message);
        self.showAlert(data.message, 'failed');
      }
    })
    .catch((error) => {
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

  render() {
    let node = this.state.node;
    const key = (this.state.node ? this.state.node._id : '') + this.state.readOnly;
    if (!node) {
      node = {
        inputs: [],
        outputs: [],
        parameters: []
      };
    }

    return (
      <HotKeys className='EditNodeMain'
               handlers={this.keyHandlers} keyMap={KEY_MAP}
      >
        <PluginsProvider value={this.props.plugins_dict}>
          {
            this.state.deprecateQuestionDialog &&
            <DeprecateDialog
              onClose={() => this.handleCloseDeprecateDialog()}
              prev_node_id={node._id}
              onDeprecate={(node_, action) => this.handleDeprecate(node_, action)}
              title={"Would you like to deprecate this Operation?"}
              />
          }
          {
            this.state.deprecateParentDialog &&
            <DeprecateDialog
              onClose={() => this.handleCloseDeprecateDialog()}
              prev_node_id={node.parent_node}
              new_node_id={node._id}
              onDeprecate={(node_, action) => this.handleDeprecate(node_, action)}
              title={"Would you like to deprecate parent Operation?"}
              />
          }
          {
            this.state.preview_text &&
            <TextViewDialog className="TextViewDialog"
              title='Preview'
              text={this.state.preview_text}
              onClose={() => this.handleClosePreview()}
            />
          }
          <div className='EditNodeHeader'>
            <PluginsConsumer>
            { plugins_dict =>
                <NodeProperties
                  title={node.title}
                  description={node.description}
                  kind={node.kind}
                  parentNode={node.parent_node}
                  successorNode={node.successor_node}
                  nodeStatus={node.node_status}
                  created={node.insertion_date}
                  updated={node.update_date}
                  onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
                  readOnly={this.state.readOnly}
                  executors_info={plugins_dict.executors_info}
                  key={key}
                 />
             }
            </PluginsConsumer>
            <ControlButtons
              onSave={() => this.handleSave()}
              onSaveApprove={() => this.handleSaveApprove()}
              onClone={() => this.handleClone()}
              onDeprecate={() => this.handleDeprecateClick()}
              onPreview={() => this.handlePreview()}
              readOnly={this.state.readOnly}
              nodeStatus={node.node_status}
              hideDeprecate={node._readonly}
              key={"controls_" + key}
            />
          </div>
          <div className='EditNodeComponents'>

            <div className='EditNodeColumn EditNodeInputs'>
              <div className='EditNodePropTitle'>
                Inputs
              </div>
              <div className='EditNodeList'>
                <InOutList
                  varName='inputs'
                  items={node.inputs}
                  key={key}
                  onChanged={(value) => this.handleParameterChanged('inputs', value)}
                  readOnly={this.state.readOnly}
                />
              </div>
            </div>

            <div className='EditNodeColumn EditNodeParameters'>
              <div className='EditNodePropTitle'>
                Parameters
              </div>
              <div className='EditNodeList'>
                <ParameterList
                  items={node.parameters}
                  key={key}
                  onChanged={(value) => this.handleParameterChanged('parameters', value)}
                  readOnly={this.state.readOnly}
                />
              </div>
            </div>

            <div className='EditNodeColumn EditNodeOutputs'>
              <div className='EditNodePropTitle'>
                Outputs
              </div>
              <div className='EditNodeList'>
                <InOutList
                  varName='outputs'
                  items={node.outputs}
                  key={key}
                  onChanged={(value) => this.handleParameterChanged('outputs', value)}
                  readOnly={this.state.readOnly}
                />
              </div>
            </div>

          </div>
        </PluginsProvider>
      </HotKeys>
    );
  }
}

Node.propTypes = {
  match: PropTypes.shape({
    params: PropTypes.shape({
      node_id: PropTypes.string
    }),
  }),
  history: PropTypes.object,
};
