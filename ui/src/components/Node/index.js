import React, { Component } from 'react';
import PropTypes from 'prop-types';
import NodeProperties from './NodeProperties';
import InOutList from './InOutList';
import ParameterList from './ParameterList';
import PreviewDialog from '../Dialogs/PreviewDialog';
import { PluginsProvider, PluginsConsumer } from '../../contexts';
import { HotKeys } from 'react-hotkeys';
import { KEY_MAP } from '../../constants';
import { addStyleToTourSteps } from '../../utils';

import './style.css';

const TOUR_STEPS = [
  {
    selector: '.EditNodeInputs',
    content: 'Here you can define all of the Inputs of this Operation. The inputs are required by default. ' +
        'Optionally your Operation can work with an array of Inputs.',
  },
  {
    selector: '.EditNodeInputs .Add',
    content: 'If the Operation is not in readonly mode, you may add extra Inputs.',
  },
  {
    selector: '.EditNodeParameters',
    content: 'The difference between Inputs and Parameters is that Parameters don`t define the structure of the Workflow. ' +
        'In the same time they are very important for Operation`s internal state.',
  },
  {
    selector: '.EditNodeParameters .parameter-_cmd',
    content: 'One of the most important parameters is _cmd. This is the code that will be executed by Plynx when you Run your Workflow.',
  },
  {
    selector: '.EditNodeOutputs',
    content: 'Configuration of Outputs is very similar to Inputs. This is what you will use to connect Operations in Workflow Editor.',
  },
  {
    selector: '.preview-button',
    content: 'If you are not sure what the script would look like when run your Operation in production, please youse Preview button.',
  },
];

export default class Node extends Component {
  constructor(props) {
    super(props);
    this.tourSteps = addStyleToTourSteps(TOUR_STEPS);
    document.title = "Node";

    this.state = {
      loading: true,
      readOnly: this.props.readOnly,
      is_workflow: this.props.is_workflow,
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
    this.loadNodeFromJson(this.props.node);
  }

  loadNodeFromJson(data) {
    console.log("loadNodeFromJson", data);
    this.node = data;
    this.setState({node: this.node});
    document.title = data.title + " - Node - PLynx";
  }

  handleParameterChanged(name, value) {
    this.node[name] = value;
    this.setState({node: this.node});
    this.props.onNodeChange(this.node);
    document.title = this.node.title + " - Node - PLynx";
  }

  handlePreview(previewData) {
    this.setState({
      previewData: previewData,
    });
  }

  handleCloseDialogs() {
    this.setState({
      previewData: null,
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
        {
            (this.state.previewData) &&
            <PreviewDialog className="PreviewDialog"
              title={this.state.previewData.title}
              file_type={this.state.previewData.file_type}
              resource_id={this.state.previewData.resource_id}
              download_name={this.state.previewData.download_name}
              onClose={() => this.handleCloseDialogs()}
            />
        }
        <PluginsProvider value={this.props.plugins_dict}>
          <div className='EditNodeHeader'>
            <PluginsConsumer>
            { plugins_dict => <NodeProperties
                  title={node.title}
                  description={node.description}
                  kind={node.kind}
                  parentNode={node.parent_node_id}
                  successorNode={node.successor_node_id}
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
                  nodeKind={node.kind}
                  onChanged={(value) => this.handleParameterChanged('inputs', value)}
                  readOnly={this.state.readOnly || this.state.is_workflow}
                  onPreview={(previewData) => this.handlePreview(previewData)}
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
                  nodeKind={node.kind}
                  onChanged={(value) => this.handleParameterChanged('outputs', value)}
                  readOnly={this.state.readOnly || this.state.is_workflow}
                  onPreview={(previewData) => this.handlePreview(previewData)}
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
  is_workflow: PropTypes.bool.isRequired,
  readOnly: PropTypes.bool.isRequired,
  node: PropTypes.object.isRequired,    // TODO more detailed
  onNodeChange: PropTypes.func.isRequired,
  plugins_dict: PropTypes.object.isRequired,    // TODO more detailed
};
