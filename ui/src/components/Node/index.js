// src/components/About/index.js
import React, { Component } from 'react';
import AlertContainer from 'react-alert-es6';
import { PLynxApi } from '../../API.js';
import NodeProperties from './NodeProperties.js'
import ControlButtons from './ControlButtons.js'
import InOutList from './InOutList.js'
import ParameterList from './ParameterList.js'
import DeprecateDialog from '../Dialogs/DeprecateDialog.js'
import TextViewDialog from '../Dialogs/TextViewDialog.js'
import LoadingScreen from '../LoadingScreen.js'
import { ObjectID } from 'bson';
import { ACTION, RESPONCE_STATUS, ALERT_OPTIONS, NODE_RUNNING_STATUS } from '../../constants.js';

import './style.css';


export default class Node extends Component {
  constructor(props) {
    super(props);
    document.title = "Node";

    this.state = {
      loading: true,
      readOnly: true,
      deprecateQuestionDialog: false,
      deprecateParentDialog: false
    }
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async componentDidMount() {
    // Loading

    var self = this;
    var loading = true;
    var node_id = this.props.match.params.node_id.replace(/\$+$/, '');
    var sleepPeriod = 1000;
    var sleepMaxPeriod = 10000;
    var sleepStep = 1000;

    var processResponse = function (response) {
      var node = response.data.data;
      self.loadNodeFromJson(node);
      if (node_id === 'new') {
        self.props.history.replace("/nodes/" + node._id);
      }
      loading = false;
    };

    var processError = function (error) {
      console.error(error);
      if (error.response.status === 404) {
        self.props.history.replace("/not_found");
        window.location.reload(false);
        loading = false;
      }
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then(function (isSuccessfull) {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.showAlert('Failed to authenticate', 'failed');
          } else {
            self.showAlert('Updated access token', 'success');
          }
        });
      }
    };

    while (loading) {
      await PLynxApi.endpoints.nodes.getOne({ id: node_id === 'new' ? 'bash_jinja2' : node_id})
      .then(processResponse)
      .catch(processError);
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

  loadNodeFromJson(data) {
    console.log("loadNodeFromJson", data);
    this.setState({node: data});
    document.title = data.title + " - Node - PLynx";
    var node_status = data.node_status;
    this.setState({readOnly: node_status !== NODE_RUNNING_STATUS.CREATED});

    var first_time_approved_node_id = window.sessionStorage.getItem('first_time_approved_state');
    if (first_time_approved_node_id === data._id) {
      this.setState({deprecateParentDialog: true})
    }
    if (first_time_approved_node_id) {
      window.sessionStorage.removeItem('first_time_approved_state');
    }
  }

  handleParameterChanged(name, value) {
    var node = this.state.node;
    node[name] = value;
    this.setState(node);
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
    var node = this.state.node;
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
    var node = this.state.node;
    if (node && node.parent_node) {
      this.setState({deprecateQuestionDialog: true});
    }
  }

  handleCloseDeprecateDialog() {
    this.setState({
      deprecateQuestionDialog: false,
      deprecateParentDialog:false
    });
  }

  handleClosePreview() {
    this.setState({preview_text: null});
  }

  handleDeprecateClick() {
    this.setState({deprecateQuestionDialog: true});
  }

  handleDeprecate(node, action) {
    this.postNode(node, true, action);
  }

  postNode(node, reloadOnSuccess, action, successCallback = null) {
    /*action might be in {'save', 'validate', 'approve', 'deprecate'}*/
    var self = this;
    self.setState({loading: true});
    PLynxApi.endpoints.nodes
    .create({
      body: {
        node: node,
        action: action
      }
    })
    .then(function (response) {
      var data = response.data;
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
        var validationErrors = data.validation_error.children;
        for (var i = 0; i < validationErrors.length; ++i) {
          var validationError = validationErrors[i];
          self.showAlert(validationError.validation_code + ': ' + validationError.object_id, 'warning');
        }

        self.showAlert(data.message, 'failed');
      } else {
        console.warn(data.message);
        self.showAlert(data.message, 'failed');
      }
    })
    .catch(function (error) {
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then(function (isSuccessfull) {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.showAlert('Failed to authenticate', 'failed');
          } else {
            self.showAlert('Failed to save the graph, please try again', 'failed');
          }
        });
      } else {
        self.showAlert('Failed to save the node', 'failed');
      }
      self.setState({loading: false});
    });
  }

  showAlert(message, type) {
    this.msg.show(message, {
      time: 5000,
      type: 'error',
      icon: <img src={"/alerts/" + type +".svg"} width="32" height="32" alt={type} />
    });
  }

  render() {
    var node = this.state.node;
    var key = (this.state.node ? this.state.node._id : '') + this.state.readOnly;
    if (!node) {
      node = {
        inputs: [],
        outputs: [],
        parameters: []
      }
    }

    return (
      <div className='EditNodeMain'>
        <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
        {this.state.loading &&
          <LoadingScreen
          ></LoadingScreen>
        }
        {
          this.state.deprecateQuestionDialog &&
          <DeprecateDialog
            onClose={() => this.handleCloseDeprecateDialog()}
            prev_node_id={node._id}
            onDeprecate={(node, action) => this.handleDeprecate(node, action)}
            title={"Would you like to deprecate this Operation?"}
            />
        }
        {
          this.state.deprecateParentDialog &&
          <DeprecateDialog
            onClose={() => this.handleCloseDeprecateDialog()}
            prev_node_id={node.parent_node}
            new_node_id={node._id}
            onDeprecate={(node, action) => this.handleDeprecate(node, action)}
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
          <NodeProperties
            title={node.title}
            description={node.description}
            base_node_name={node.base_node_name}
            parentNode={node.parent_node}
            successorNode={node.successor_node}
            nodeStatus={node.node_status}
            created={node.insertion_date}
            updated={node.update_date}
            onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
            readOnly={this.state.readOnly}
            key={key}
          />
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
      </div>
    );
  }
}
