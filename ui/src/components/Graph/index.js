/* eslint max-lines: 0 */
/* eslint complexity: 0 */


import React, { Component } from 'react';
import PropTypes from 'prop-types';
import ReactNodeGraph from '../3rd_party/react_node_graph';
import { typesValid } from '../../graphValidation';
import cookie from 'react-cookies';
import HubPanel from './HubPanel';
import PreviewDialog from '../Dialogs/PreviewDialog';
import PropertiesBar from './PropertiesBar';
import withDragDropContext from './withDragDropContext';
import FileDialog from '../Dialogs/FileDialog';
import CodeDialog from '../Dialogs/CodeDialog';
import ParameterSelectionDialog from '../Dialogs/ParameterSelectionDialog';
import {ObjectID} from 'bson';
import {HotKeys} from 'react-hotkeys';
import {
  VALIDATION_CODES,
  NODE_RUNNING_STATUS,
  SPECIAL_TYPE_NAMES,
  KEY_MAP,
  SPECIAL_NODE_IDS,
} from '../../constants';
import { API_ENDPOINT } from '../../configConsts';
import { storeToClipboard, loadFromClipboard, addStyleToTourSteps } from '../../utils';

import "./gridtile.png";
import "./node.css";
import "./style.css";

function parameterIsSpecial(parameter) {
  return SPECIAL_TYPE_NAMES.indexOf(parameter.parameter_type) > -1 && parameter.widget !== null;
}

const TOUR_STEPS = [
  {
    selector: '',
    content: 'Welcome to Plynx! This tour will walk you through the main concepts and components of the interface.',
  },
  {
    selector: '.hub-entry-list',
    content: 'This toolbar contains all the Operations you need to build your workflow. All you need to do is to drag and drop Operations to the editor.',
  },
  {
    selector: '.NodeItem',
    content: 'Plynx is an open modular platform. Each Operaion represents an executable code or function, business logic, transformation, etc. ' +
        'They can be defined eigher by users, admins, or imported from public library.',
  },
  {
    selector: '.GraphRoot',
    content: 'Workflow Editor has a central place in Plynx. ' +
        'It allows you to easily build new pipelines, improve existing ones or create new experiments with the workflow.',
  },
  {
    selector: '.GraphRoot .node',
    content: 'Plynx is domain and framework agnostic platform. ' +
        'Operation can be a python script, API call, model inference function, interaction with other services, etc. ' +
        'The complexity under the hood does not matter.  What matters is what role it plays in your workflow.',
  },
  {
    selector: '.GraphRoot .connector',
    content: 'The relations between Operations are defined by the edges. ' +
        'Depending on the use case, the entire Workflow will be exectuded in multiple independent containers, ' +
        'compiled to a single executable file for higher performance or converted into Spark or AWS Step Functions workflow.',
  },
  {
    selector: '.PropertiesBar',
    content: 'This toolbar contains properties of Workflow or Operations. Feel free to customize your Workflows in an intuitive way. ' +
        'You may change target variable, number of hidden layers, aggregation function, model version, etc.',
  },
  {
    selector: '.ParameterItem',
    content: 'The Parameters are customizable. Depending on use case, it can be a string, number, enum, list, or even code. ' +
        'You may also override their values base on global Workflow-level Parameters.',
  },
  {
    selector: '.control-panel',
    content: 'Control panel contains multiple operations you may find useful such as Workflow validation or upgrating Operaions to new versions.',
  },
  {
    selector: '.control-toggle',
    content: 'Working with Workflows is not limited by Editor alone. You may define Workflow-level Parameters or monitor running or explore completed Runs.',
  },
  {
    selector: '.run-button',
    content: 'Don`t forget to try to execute the Workflow to see Plynx in action!',
  },
];

class Graph extends Component {
  static propTypes = {
    showAlert: PropTypes.func.isRequired,
    onNodeChange: PropTypes.func.isRequired,
    node: PropTypes.object.isRequired,
    editable: PropTypes.bool.isRequired,
    selectedNode: PropTypes.string,
  }

  constructor(props) {
    super(props);
    this.graph_node = {};
    this.tourSteps = addStyleToTourSteps(TOUR_STEPS);
    this.selectedNode = this.props.selectedNode;
    document.title = "Graph";

    this.state = {
      nodes: [],
      connections: [],
      graph: {},
      graphId: null,
      editable: null,
      loading: true,
      title: "",
      description: "",
      graphRunningStatus: null,
      previewData: null,
      generatedCode: "",
      linkParameters: null,
      nodeDis: props.nodeDis,
    };

    let token = cookie.load('refresh_token');
    // TODO remove after demo
    if (token === 'Not assigned') {
      token = cookie.load('access_token');
    }

    this.generatedCodeHeader =
`#!/usr/bin/env python
from plynx.api import Operation, File, Graph, Client
TOKEN = '` + token + `'
ENDPOINT = '` + API_ENDPOINT + `'
`;
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async componentDidMount() {
    // Loading

    this.loadGraphFromJson(this.props.node);
  }

  loadGraphFromJson(data) {
    this.graph_node = data;
    document.title = this.graph_node.title + " - Graph - PLynx";
    console.log(this.graph_node);
    this.node_lookup = {};
    this.connections = [];
    const parameterNameToGraphParameter = {};
    const ts = new ObjectID().toString();

    this.nodes = this.graph_node.parameters.find(p => p.name === '_nodes').value.value;

    let parameter;
    for (parameter of this.graph_node.parameters) {
      parameterNameToGraphParameter[parameter.name] = parameter;
    }

    let inputNode = null;
    for (let i = 0; i < this.nodes.length; ++i) {
      const node = this.nodes[i];
      node._ts = ts;

      // Remove broken references
      for (parameter of node.parameters) {
        if (parameter.reference &&
            (!parameterNameToGraphParameter.hasOwnProperty(parameter.reference)
                || parameter.parameter_type !== parameterNameToGraphParameter[parameter.reference].parameter_type
            )
        ) {
          parameter.reference = null;
        }
      }

      // work with input and output
      if (node._id === SPECIAL_NODE_IDS.INPUT) {
        inputNode = node;
        node.outputs = this.graph_node.inputs;
      } else if (node._id === SPECIAL_NODE_IDS.OUTPUT) {
        const prevInputToInputReferences = {};

        let jj;
        for (jj = 0; jj < node.inputs.length; ++jj) {
          const input = node.inputs[jj];
          prevInputToInputReferences[input.name + input.file_type] = input.input_references;
        }
        node.inputs = this.graph_node.outputs.map(
              (output) => {
                return {
                  name: output.name,
                  file_type: output.file_type,
                  values: output.values,
                  input_references:
                    prevInputToInputReferences[output.name + output.file_type] ? prevInputToInputReferences[output.name + output.file_type] : [],
                  min_count: output.min_count,
                  is_array: output.is_array,
                };
              }
          );
      }
      this.node_lookup[node._id] = node;
    }

    let i = 0;
    for (i = 0; i < this.nodes.length; ++i) {
      const node = this.nodes[i];
      const blockInputs = [];
      const blockOutputs = [];
      const specialParameterNames = [];
      let j = 0;

      for (j = 0; j < node.inputs.length; ++j) {
        blockInputs.push({
          name: node.inputs[j].name,
          file_type: node.inputs[j].file_type,
          is_array: node.inputs[j].is_array,
        });
        const inputValueIndexToRemove = [];
        for (let k = 0; k < node.inputs[j].input_references.length; ++k) {
          const from_block = node.inputs[j].input_references[k].node_id;
          const from = node.inputs[j].input_references[k].output_id;

          if (from_block === SPECIAL_NODE_IDS.INPUT && inputNode) {
            const output = inputNode.outputs.filter((out) => out.name === from);
            if (output.length === 0 || !typesValid(output[0], node.inputs[j])) {
              inputValueIndexToRemove.push(k);
              continue;
            }
          }
          this.connections.push({
            "from_block": from_block,
            "from": from,
            "to_block": node._id,
            "to": node.inputs[j].name}
              );
        }
        for (let v = inputValueIndexToRemove.length - 1; v >= 0; --v) {
          node.inputs[j].input_references.splice(inputValueIndexToRemove[v], 1);
        }
      }
      for (j = 0; j < node.outputs.length; ++j) {
        blockOutputs.push({
          name: node.outputs[j].name,
          file_type: node.outputs[j].file_type,
          is_array: node.outputs[j].is_array,
        });
      }

      for (j = 0; j < node.parameters.length; ++j) {
        if (parameterIsSpecial(node.parameters[j])) {
          specialParameterNames.push(node.parameters[j].name);
        }
      }

      if (!node.hasOwnProperty("x")) {
        node.x = Math.floor(Math.random() * 800) + 1;
      }
      if (!node.hasOwnProperty("y")) {
        node.y = Math.floor(Math.random() * 400) + 1;
      }
    }

    this.setState({
      nodes: this.nodes,
      connections: this.connections,
      graph: this.graph_node,
      editable: this.props.editable,

    }, () => {
      if (this.selectedNode) {
        this.mainGraph.getDecoratedComponentInstance().selectBlocks([this.selectedNode]);
        this.selectedNode = null;
      }
    });
  }

  updateGraphFromJson(newGraph) {
    console.log("update", newGraph.node_running_status);
    let i = 0;

    const newNodes = newGraph.parameters.find((p) => p.name === '_nodes').value.value;

    for (i = 0; i < newNodes.length; ++i) {
      this.node_lookup[newNodes[i]._id] = newNodes[i];
    }

    this.graph_node = newGraph;

    this.setState({
      nodes: newNodes,
    });
  }

  onNewConnector(from_nid, from_pin, to_nid, to_pin) {
    const from_node = this.node_lookup[from_nid];
    const node_output = from_node.outputs.find(
      (node_output_) => {
        return node_output_.name === from_pin;
      }
    );

    const to_node = this.node_lookup[to_nid];
    const node_input = to_node.inputs.find(
      (node_input_) => {
        return node_input_.name === to_pin;
      }
    );

    if (!node_input) {
      throw new Error("Node input with name '" + to_pin + "' not found");
    }
    if (!node_output) {
      throw new Error("Node input with name '" + from_pin + "' not found");
    }

    if (!node_input.is_array && node_input.input_references.length > 0) {
      this.props.showAlert("No more slots for new connections left", 'warning');
      return;
    }

    if (!typesValid(node_output, node_input)) {
      this.props.showAlert("Incompatible types", 'warning');
      return;
    }

    if (node_input.input_references.filter(
        (a) => a.node_id === from_nid && a.output_id === from_pin).length > 0) {
      this.props.showAlert("Connection already exists", 'warning');
      return;
    }

    this.connections.push({
      from_block: from_nid,
      from: from_pin,
      to_block: to_nid,
      to: to_pin
    });

    node_input.input_references.push({
      "node_id": from_nid,
      "output_id": from_pin
    });

    if (this.node_lookup[to_nid]._highlight) {
      this.node_lookup[to_nid]._highlight = false;
      this.setState({
        nodes: this.nodes,
      });
    }

    this.setState({connections: this.connections});

    this.props.onNodeChange(this.graph_node);
  }

  onRemoveConnector(connector) {
    console.log('Remove connector', connector);
    let connections = this.connections;
    connections = connections.filter((connection) => {
      return connection !== connector;
    });

    const to_node = this.node_lookup[connector.to_block];
    const input = to_node.inputs.find((input_) => {
      return input_.name === connector.to;
    });
    input.input_references = input.input_references.filter((value) => {
      return !(value.output_id === connector.from && value.node_id === connector.from_block);
    });

    this.connections = connections;
    this.setState({connections: connections});

    this.props.onNodeChange(this.graph_node);
  }

  onRemoveBlock(nid) {
    console.log('Remove block', nid);
    if (this.node_lookup[nid].node_running_status === NODE_RUNNING_STATUS.SPECIAL) {
      console.log('Cannot remove special node');
      return;
    }

    this.nodes.splice(
        this.nodes.map(node => node._id === nid).indexOf(true),     // simply indexOf does not work!
        1
    );

    delete this.node_lookup[nid];

    this.setState({
      nodes: this.nodes,
    });

    this.props.onNodeChange(this.graph_node);
  }

  onCopyBlock(copyList, offset) {
    const nodes = copyList.nids.map(nid => this.node_lookup[nid]).filter((node) => node && node.node_running_status !== NODE_RUNNING_STATUS.SPECIAL);
    const copyObject = {
      nodes: nodes,
      connectors: copyList.connectors,
      offset: offset,
    };
    console.log(copyList.nids, copyObject);

    storeToClipboard(copyObject);
  }

  onPasteBlock(offset) {
    const copyBody = loadFromClipboard();
    const nidOldToNew = {};
    if (!copyBody) {
      return;
    }
    let ii;
    const pastedBlockIds = [];
    this.mainGraph.getDecoratedComponentInstance().deselectAll(false);
    for (ii = 0; ii < copyBody.nodes.length; ++ii) {
      const blockJson = copyBody.nodes[ii];
      const block_id = this.handleDrop(
        {
          nodeContent: blockJson,
          mousePos: {
            x: blockJson.x + 380 + offset.x - copyBody.offset.x,
            y: blockJson.y + 120 + offset.y - copyBody.offset.y,
          },
        },
        false);
      nidOldToNew[blockJson._id] = block_id;
      pastedBlockIds.push(block_id);
    }
    for (ii = 0; ii < copyBody.connectors.length; ++ii) {
      const connector = copyBody.connectors[ii];
      let { to_block, from_block } = connector;
      if (nidOldToNew.hasOwnProperty(to_block)) {
        to_block = nidOldToNew[to_block];
      }
      if (nidOldToNew.hasOwnProperty(from_block)) {
        from_block = nidOldToNew[from_block];
      }
      const from_node = this.node_lookup[from_block];
      const to_node = this.node_lookup[to_block];
      if (from_node && to_node) {
        let from_index = -1;
        let to_index = -1;
        let jj;
        for (jj = 0; jj < from_node.outputs.length; ++jj) {
          if (from_node.outputs[jj].name === connector.from) {
            from_index = jj;
            break;
          }
        }
        for (jj = 0; jj < to_node.inputs.length; ++jj) {
          if (to_node.inputs[jj].name === connector.to) {
            to_index = jj;
            break;
          }
        }

        if (to_index < 0 || from_index < 0) {
          console.log(`Index not found for connector ${connector}`);
          continue;
        }
        if (!to_node.inputs[to_index].is_array && to_node.inputs[to_index].input_references.length > 0) {
          continue;
        }

        to_node.inputs[to_index].input_references.push({
          "node_id": from_node._id,
          "output_id": connector.from,
        });

        this.connections.push({
          "from_block": from_node._id,
          "from": connector.from,
          "to_block": to_node._id,
          "to": connector.to,
        });
      }
    }
    this.mainGraph.getDecoratedComponentInstance().selectBlocks(pastedBlockIds);
    this.setState({
      nodes: this.nodes,
      connections: this.connections,
    });

    this.props.onNodeChange(this.graph_node);
  }

  onOutputClick(nid, outputIndex) {
    if (!this.node_lookup.hasOwnProperty(nid)) {
      console.error("Cannot find node with id " + nid);
      return;
    }
    const node = this.node_lookup[nid];
    const output = node.outputs[outputIndex];
    if (output.values.length > 0) {
      this.handlePreview({
        title: output.name,
        file_type: output.file_type,
        resource_id: output.values[0],
        download_name: output.name,
      });
    } else {
      console.log("Resource is not ready yet");
    }
  }

  onSpecialParameterClick(nid, specialParameterIndex) {
    if (!this.node_lookup.hasOwnProperty(nid)) {
      console.error("Cannot find node with id " + nid);
      return;
    }
    const node = this.node_lookup[nid];
    let idx = 0;
    for (let i = 0; i < node.parameters.length; ++i) {
      if (parameterIsSpecial(node.parameters[i])) {
        if (idx === specialParameterIndex) {
          this.setState({
            nodeId: nid,
            parameterName: node.parameters[i].name,
            parameterValue: node.parameters[i].value,
          });
        }
        ++idx;
      }
    }
  }

  onBlockMove(nid, pos) {
    console.log('end move : ' + nid, pos);
    if (!this.node_lookup.hasOwnProperty(nid)) {
      console.error("Cannot find node with id " + nid);
      return;
    }
    const node = this.node_lookup[nid];
    node.x = pos.x;
    node.y = pos.y;

    this.props.onNodeChange(this.graph_node);
  }

  handleBlocksSelect(nids) {
    console.log('blocks selected : ' + nids);

    this.selectedNodeIds = nids;

    if (nids.length === 1) {
      const nid = nids[0];
      const node = this.node_lookup[nid];
      if (node) {
        this.propertiesBar.setNodeData(node);

        if (this.node_lookup[nid]._highlight) {
          this.node_lookup[nid]._highlight = false;
          this.setState({
            nodes: this.nodes,
          });
        }
      }
    } else if (nids.length > 1) {
      this.propertiesBar.setNodeDataArr(nids.map((nid) => this.node_lookup[nid]));
    } else {
      this.propertiesBar.setNodeData(this.graph_node);
    }
  }

  handleParameterChanged(node_ids, name, value) {
    for (let ii = 0; ii < node_ids.length; ++ii) {
      const node_id = node_ids[ii];
      let node;
      if (node_id in this.node_lookup) {
        node = this.node_lookup[node_id];
      } else {
        node = this.graph_node;
      }
      const node_parameter = node.parameters.find(
          (param) => {
            return param.name === name;
          }
        );
      if (node_parameter) {
        node_parameter.value = value;
      } else if (name === '_DESCRIPTION' || name === '_TITLE') {
        const inName = name.substring(1, name.length).toLowerCase();
        const block = this.node_lookup[node_id];
        node[inName] = value;

        document.title = this.graph_node.title + " - Graph - PLynx";
        if (block) { // the case of graph itself
          block[inName] = value;
        } else {
          // using for node, it is hard to update descriptions
          this.setState({graph: this.graph_node});
        }
      } else {
        throw new Error("Parameter not found");
      }
    }
    this.props.onNodeChange(this.graph_node);
  }

  handlePreview(previewData) {
    this.setState({
      previewData: previewData,
    });
  }

  handleClosePreview() {
    this.setState({
      previewData: undefined,
    });
  }

  handleCloseCodeDialog() {
    this.setState({
      nodeId: undefined,
      parameterName: undefined,
      parameterValue: undefined,
    });
  }

  handleCloseGeneratedCodeDialog() {
    this.setState({
      generatedCode: undefined,
    });
  }

  handleShowFile(nid) {
    this.setState({
      fileObj: this.node_lookup[nid]
    });
  }

  handleCloseFileDialog() {
    this.setState({
      fileObj: null
    });
  }

  handleLinkClick(node_ids, name) {
    this.link_node_parameters = [];
    let parameter_reference;
    let parameter_type;
    let node_id;
    for (node_id of node_ids) {
      const node = this.node_lookup[node_id];
      const node_parameter = node.parameters.find(
          (param) => {
            return param.name === name;
          }
        );
      if (!node_parameter) {
        throw new Error("Parameter not found");
      }

      parameter_reference = node_parameter.reference;

      parameter_type = node_parameter.parameter_type;

      this.link_node_parameters.push(node_parameter);
    }

    this.link_graph_parameters = [{
      name: null,
      parameter_type: "none",
      value: "0",
      mutable_type: true,
      removable: true,
      publicable: true,
      widget: "None",
    }].concat(
        this.graph_node.parameters.filter((parameter) => parameter.parameter_type === parameter_type && parameter.widget)
    );

    let linkParametersIndex = 0;
    if (parameter_reference) {
      linkParametersIndex = this.link_graph_parameters.findIndex((parameter) => parameter.name === parameter_reference);
    }

    this.setState({
      linkParameters: this.link_graph_parameters,
      linkParametersIndex: linkParametersIndex,
    });
  }

  handleIndexLinkChange(index) {
    let node_parameter;
    for (node_parameter of this.link_node_parameters) {
      node_parameter.reference = this.link_graph_parameters[index].name;
    }
    this.handleBlocksSelect(this.selectedNodeIds);
    this.props.onNodeChange(this.graph_node);
  }

  handleCloseParameterLinkDialog() {
    this.setState({
      linkParameters: null
    });
  }

  closeAllDialogs() {
    this.handleClosePreview();
    this.handleCloseCodeDialog();
    this.handleCloseGeneratedCodeDialog();
    this.handleCloseFileDialog();
    this.handleCloseParameterLinkDialog();
  }

  keyHandlers = {
    escPressed: () => {
      this.closeAllDialogs();
    },
  }

  handleDrop(blockObjArg, replaceOriginalNode) {
    const blockObj = JSON.parse(JSON.stringify(blockObjArg)); // copy
    const node = blockObj.nodeContent;
    const inputs = [];
    const outputs = [];
    const specialParameterNames = [];

    let i = 0;

    if (replaceOriginalNode) {
      node.original_node_id = node._id;
    }
    node.parent_node_id = null;
    node.successor_node_id = null;
    node._id = new ObjectID().toString();

    if (node.inputs) {
      for (i = 0; i < node.inputs.length; ++i) {
        inputs.push({
          name: node.inputs[i].name,
          file_type: node.inputs[i].file_type,
          is_array: node.inputs[i].is_array,
        });
        node.inputs[i].values = []; // clear inputs on paste
        node.inputs[i].input_references = [];
      }
    }
    for (i = 0; i < node.outputs.length; ++i) {
      outputs.push({
        name: node.outputs[i].name,
        file_type: node.outputs[i].file_type,
        is_array: node.outputs[i].is_array,
      });
      if (node.node_running_status !== NODE_RUNNING_STATUS.STATIC) {
        node.outputs[i].values = []; // clear outputs
      }
    }
    for (i = 0; i < node.logs.length; ++i) {
      node.logs[i].values = []; // clear outputs
    }
    for (i = 0; i < node.parameters.length; ++i) {
      if (parameterIsSpecial(node.parameters[i])) {
        specialParameterNames.push(node.parameters[i].name);
      }
    }
    node.x = Math.max(blockObj.mousePos.x - 340, 0);
    node.y = Math.max(blockObj.mousePos.y - 80, 0);

    if (node.node_running_status !== NODE_RUNNING_STATUS.STATIC) {
      node.node_running_status = NODE_RUNNING_STATUS.CREATED;
    }
    node.cache_url = null;

    this.node_lookup[node._id] = node;

    this.nodes.push(node);
    console.log("node", node);

    this.setState({
      nodes: this.nodes,
      connections: this.connections,
    });

    this.props.onNodeChange(this.graph_node);

    return node._id;
  }

  showValidationError(validationError) {
    for (let ii = 0; ii < validationError.children.length; ++ii) {
      const child = validationError.children[ii];
      let nodeId = null;
      let node = null;
      switch (child.validation_code) {
        case VALIDATION_CODES.IN_DEPENDENTS:
          this.showValidationError(child);
          break;
        case VALIDATION_CODES.DEPRECATED_NODE:
          nodeId = validationError.object_id;
          node = this.node_lookup[nodeId];

          this.node_lookup[nodeId]._highlight = true;
          this.setState({
            nodes: this.nodes,
          });

          this.props.showAlert("Deprecated Node found: `" + node.title + "`", 'warning');
          break;
        case VALIDATION_CODES.MISSING_INPUT:
          nodeId = validationError.object_id;
          node = this.node_lookup[nodeId];

          this.node_lookup[nodeId]._highlight = true;
          this.setState({
            nodes: this.nodes,
          });

          this.props.showAlert("Missing input `" + child.object_id + "` in node `" + node.title + "`", 'warning');
          break;
        case VALIDATION_CODES.MISSING_PARAMETER:
          this.props.showAlert("Missing parameter `" + child.object_id + "`", 'warning');
          break;
        case VALIDATION_CODES.EMPTY_GRAPH:
          this.props.showAlert("The graph is empty", 'warning');
          break;
        default:
      }
    }
  }

  render() {
    return (
    <HotKeys className="GraphNode"
             handlers={this.keyHandlers} keyMap={KEY_MAP}
    >
        <div className={'BackgroundLabels ' + (this.state.editable ? 'editable' : 'readonly')}>
          <div className="Title">{this.state.graph.title}</div>
          <div className="Description">&ldquo;{this.state.graph.description}&rdquo;</div>
        </div>
        {this.state.fileObj &&
          <FileDialog
            onClose={() => this.handleCloseFileDialog()}
            onDeprecate={(fileObj) => this.handleDeprecate(fileObj)}
            fileObj={this.state.fileObj}
            hideDeprecate  // TODO let the author to deprecate file
            onPreview={(previewData) => this.handlePreview(previewData)}
            />
        }
        {
          (this.state.previewData) &&
          <PreviewDialog className="PreviewDialog"
            title={this.state.previewData.title}
            file_type={this.state.previewData.file_type}
            resource_id={this.state.previewData.resource_id}
            download_name={this.state.previewData.download_name}
            onClose={() => this.handleClosePreview()}
          />
        }
        {
          (this.state.nodeId && this.state.parameterName) &&
          <CodeDialog
            title={this.state.parameterName}
            value={this.state.parameterValue}
            onClose={() => this.handleCloseCodeDialog()}
            readOnly={!this.state.editable}
            onParameterChanged={(value) => this.handleParameterChanged(this.state.nodeId, this.state.parameterName, value)}
          />
        }
        {
          this.state.generatedCode &&
          <CodeDialog
            title={"API Code"}
            value={{
              mode: "python",
              value: this.generatedCodeHeader + this.state.generatedCode,
            }}
            onClose={() => this.handleCloseGeneratedCodeDialog()}
            readOnly
          />
        }
        {
            this.state.linkParameters &&
            <ParameterSelectionDialog
              title={"Link Graph parameter"}
              parameters={this.state.linkParameters}
              index={this.state.linkParametersIndex}
              onClose={() => this.handleCloseParameterLinkDialog()}
              onIndexChanged={(index) => this.handleIndexLinkChange(index)}
              readOnly={!this.state.editable}
            />
        }

        {/* Visible and flex layout blocks */}
        {this.state.editable && <HubPanel kind={this.state.graph.kind} />}

        <ReactNodeGraph className="MainGraph"
          ref={(child) => {
            this.mainGraph = child;
          }}
          data={this.state}
          graphId={this.state.graphId}
          editable={this.state.editable}
          onBlockMove={(nid, pos) => this.onBlockMove(nid, pos)}
          onNewConnector={(n1, o, n2, i) => this.onNewConnector(n1, o, n2, i)}
          onRemoveConnector={(connector) => this.onRemoveConnector(connector)}
          onOutputClick={(nid, outputIndex) => this.onOutputClick(nid, outputIndex)}
          onSpecialParameterClick={(nid, specialParameterIndex) => this.onSpecialParameterClick(nid, specialParameterIndex)}
          onRemoveBlock={(nid) => this.onRemoveBlock(nid)}
          onCopyBlock={(copyList, offset) => this.onCopyBlock(copyList, offset)}
          onPasteBlock={(offset) => this.onPasteBlock(offset)}
          onBlocksSelect={(nids) => {
            this.handleBlocksSelect(nids);
          }}
          onDrop={(nodeObj) => this.handleDrop(nodeObj, true)}
          onAllBlocksDeselect={() => this.handleBlocksSelect([])}
          onSavePressed={() => this.handleSave()}
          key={'graph' + this.state.editable}
          nodeDis={this.state.nodeDis}
        />

        { this.state.editable !== null &&
        <PropertiesBar className="PropertiesBar"
                      ref={(child) => {
                        this.propertiesBar = child;
                      }}
                      onParameterChanged={(node_ids, name, value) => this.handleParameterChanged(node_ids, name, value)}
                      editable={this.state.editable}
                      initialNode={this.graph_node}
                      onPreview={(previewData) => this.handlePreview(previewData)}
                      key={"prop" + this.state.editable}
                      onFileShow={(nid) => this.handleShowFile(nid)}
                      onLinkClick={(node_ids, name) => this.handleLinkClick(node_ids, name)}
        />
        }
    </HotKeys>
    );
  }
}


export default withDragDropContext(Graph);