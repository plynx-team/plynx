import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { PLynxApi } from '../../API';
import NodeProperties from './NodeProperties';
import ControlButtons from './ControlButtons';
import InOutList from './InOutList';
import ParameterList from './ParameterList';
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
                  parentNode={node.parent_node_id}
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
