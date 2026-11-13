import React, { Component } from 'react';
import NodeProperties from './NodeProperties';
import InOutList from './InOutList';
import ParameterList from './ParameterList';
import PreviewDialog from '../Dialogs/PreviewDialog';
import { PluginsProvider, PluginsConsumer } from '../../contexts';
import HotKeys from '../Common/HotKeys';
import { KEY_MAP } from '../../constants';
import { addStyleToTourSteps, TourStep } from '../../utils';
import { NodeData, PluginsDict, PreviewData } from '../../types';

import './style.css';

const TOUR_STEPS: TourStep[] = [
  {
    selector: '.EditNodeInputs',
    content:
      'Here you can define all of the Inputs of this Operation. The inputs are required by default. ' +
      'Optionally your Operation can work with an array of Inputs.',
  },
  {
    selector: '.EditNodeInputs .Add',
    content: 'If the Operation is not in readonly mode, you may add extra Inputs.',
  },
  {
    selector: '.EditNodeParameters',
    content:
      'The difference between Inputs and Parameters is that Parameters don`t define the structure of the Workflow. ' +
      'In the same time they are very important for Operation`s internal state.',
  },
  {
    selector: '.EditNodeParameters .parameter-_cmd',
    content:
      'One of the most important parameters is _cmd. This is the code that will be executed by Plynx when you Run your Workflow.',
  },
  {
    selector: '.EditNodeOutputs',
    content:
      'Configuration of Outputs is very similar to Inputs. This is what you will use to connect Operations in Workflow Editor.',
  },
  {
    selector: '.preview-button',
    content:
      'If you are not sure what the script would look like when run your Operation in production, please youse Preview button.',
  },
];

export interface NodeComponentProps {
  match?: any;
  history?: any;
  is_workflow: boolean;
  is_graph?: boolean;
  readOnly: boolean;
  node: NodeData;
  onNodeChange: (node: NodeData) => void;
  plugins_dict: PluginsDict;
}

interface NodeComponentState {
  loading: boolean;
  readOnly: boolean;
  is_workflow: boolean;
  node?: NodeData;
  previewData?: PreviewData | null;
}

export default class Node extends Component<NodeComponentProps, NodeComponentState> {
  tourSteps: TourStep[];
  node: NodeData;

  constructor(props: NodeComponentProps) {
    super(props);
    this.tourSteps = addStyleToTourSteps(TOUR_STEPS);
    document.title = 'Node';
    this.node = props.node;

    this.state = {
      loading: true,
      readOnly: this.props.readOnly,
      is_workflow: this.props.is_workflow,
      node: this.props.node,
      previewData: null,
    };
  }

  keyHandlers = {
    escPressed: () => {
      this.handleCloseDialogs();
    },
  };

  componentDidMount() {
    this.loadNodeFromJson(this.props.node);
  }

  componentDidUpdate(prevProps: NodeComponentProps) {
    if (prevProps.node !== this.props.node) {
      this.loadNodeFromJson(this.props.node);
    }
  }

  loadNodeFromJson(data: NodeData) {
    this.node = data;
    this.setState({ node: this.node });
    document.title = `${data.title} - Node - PLynx`;
  }

  handleParameterChanged(name: string, value: any) {
    this.node = { ...this.node, [name]: value };
    this.setState({ node: this.node });
    this.props.onNodeChange(this.node);
    document.title = `${this.node.title} - Node - PLynx`;
  }

  handlePreview(previewData: PreviewData) {
    this.setState({
      previewData,
    });
  }

  handleCloseDialogs() {
    this.setState({
      previewData: null,
    });
  }

  render() {
    let node = this.state.node;
    const key = (this.state.node ? this.state.node._id : '') + String(this.state.readOnly);
    if (!node) {
      node = {
        _id: '',
        title: '',
        kind: '',
        inputs: [],
        outputs: [],
        parameters: [],
      };
    }

    return (
      <HotKeys className="EditNodeMain" handlers={this.keyHandlers} keyMap={KEY_MAP}>
        {this.state.previewData && (
          <PreviewDialog
            className="PreviewDialog"
            title={this.state.previewData.title}
            file_type={this.state.previewData.file_type}
            resource_id={this.state.previewData.resource_id}
            values={this.state.previewData.values}
            display_raw={this.state.previewData.display_raw}
            is_array={this.state.previewData.is_array}
            download_name={this.state.previewData.download_name}
            onClose={() => this.handleCloseDialogs()}
          />
        )}
        <PluginsProvider value={this.props.plugins_dict}>
          <div className="EditNodeHeader">
            <PluginsConsumer>
              {(plugins_dict: PluginsDict) => (
                <NodeProperties
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
              )}
            </PluginsConsumer>
          </div>
          <div className="EditNodeComponents">
            <div className="EditNodeColumn EditNodeInputs">
              <div className="EditNodePropTitle">Inputs</div>
              <div className="EditNodeList">
                <InOutList
                  varName="inputs"
                  items={node.inputs}
                  key={key}
                  nodeKind={node.kind}
                  onChanged={(value) => this.handleParameterChanged('inputs', value)}
                  readOnly={this.state.readOnly || this.state.is_workflow}
                  onPreview={(previewData) => this.handlePreview(previewData)}
                />
              </div>
            </div>

            <div className="EditNodeColumn EditNodeParameters">
              <div className="EditNodePropTitle">Parameters</div>
              <div className="EditNodeList">
                <ParameterList
                  items={node.parameters}
                  key={key}
                  onChanged={(value) => this.handleParameterChanged('parameters', value)}
                  readOnly={this.state.readOnly}
                />
              </div>
            </div>

            <div className="EditNodeColumn EditNodeOutputs">
              <div className="EditNodePropTitle">Outputs</div>
              <div className="EditNodeList">
                <InOutList
                  varName="outputs"
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
