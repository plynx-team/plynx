/* eslint max-lines: 0 */
/* eslint complexity: 0 */

import React, { Component, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { typesValid } from '../../graphValidation';
import cookie from 'react-cookies';
import HubPanel from './HubPanel';
import PreviewDialog from '../Dialogs/PreviewDialog';
import PropertiesBar from './PropertiesBar';
//import withDragDropContext from './withDragDropContext';
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

import ReactFlow, { Controls, Background, MiniMap, ReactFlowProvider, fitView, useNodesState, useEdgesState, useReactFlow, applyNodeChanges } from 'reactflow';
import styled, { ThemeProvider } from 'styled-components';
import OperationNode from './nodes/OperationNode';
import 'reactflow/dist/style.css';

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

const nodeTypes = {
  operation: OperationNode,
};

const minimapStyle = {
  height: 120,
  backgroundColor: "black",
};

const proOptions = { hideAttribution: true };

const ControlsStyled = styled(Controls)`
  button {
    background-color: #2b2b2b;
    color: #eee;
    border-bottom: 1px solid #444;

    &:hover {
      background-color: #444;
    }

    path {
      fill: currentColor;
    }
  }
`;

const ChangeType = {
  DELETE_EDGE: "DELETE_EDGE",
  CREATE_EDGE: "CREATE_EDGE",
  MOVE_NODE: "MOVE_NODE",
  DELETE_NODE: "DELETE_NODE",
  DROP_NODE: "DROP_NODE",
  SELECT_NODE: "SELECT_NODE",
  DESELECT_NODE: "DESELECT_NODE",
};

class Graph extends Component {
  static propTypes = {
    showAlert: PropTypes.func.isRequired,
    onNodeChange: PropTypes.func.isRequired,
    node: PropTypes.object.isRequired,
    editable: PropTypes.bool.isRequired,
    selectedNode: PropTypes.string,
  };

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
      flowNodes: [],
      flowEdges: [],
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

    this.reactFlowInstance = React.createRef();
    this.reactFlowWrapper = React.createRef();
    this.selectedNodeIds = new Set();
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async componentDidMount() {
    // Loading
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

    //---------------------- down
    var flowNodes = [];
    var flowEdges = [];
    for (var ii = 0; this.nodes && ii < this.nodes.length; ++ii) {
      const node = this.nodes[ii];
      flowNodes.push(this.nodeToFlowNode(node));

      for (var jj = 0; jj < node.inputs.length; ++jj) {
        const input = node.inputs[jj];
        console.log(input);
        for (var kk = 0; kk < input.input_references.length; ++kk) {
            const input_reference = input.input_references[kk];
            flowEdges.push({
                id: `${input_reference.node_id}-${node._id}-${input.name}-${input_reference.output_id}`,
                source: input_reference.node_id,
                target: node._id,
                sourceHandle: input_reference.output_id,
                targetHandle: input.name,
                // style: {
                //     strokeWidth: 4,
                //     stroke: `#${intToRGB(hashCode(input_reference.node_id + input_reference.name))}`,
                // },
                interactionWidth: 6,
            });
            console.log(input_reference, input_reference.name);
        }

      }
    }
    if (this.reactFlowInstance) {
      this.reactFlowInstance.setNodes(flowNodes);
      this.reactFlowInstance.setEdges(flowEdges);
      //this.reactFlowInstance.fitView();
    }

    //---------------------- up

    console.log("$$$", this.reactFlowInstance);

    this.setState({
      nodes: this.nodes,
      connections: this.connections,
      graph: this.graph_node,
      editable: this.props.editable,
      flowNodes: flowNodes,
      flowEdges: flowEdges,

    }, () => {
      if (this.selectedNode) {
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
    this.reactFlowInstance.setNodes(newNodes.map(node => this.nodeToFlowNode(node)));

    this.setState({
      nodes: newNodes,
    });
  }

  syncNodes(newNodes) {
    let i;
    const newNodesLookup = {};

    for (i = 0; i < newNodes.length; ++i) {
      newNodesLookup[newNodes[i]._id] = newNodes[i];
    }

    for (i = 0; i < this.nodes.length; ++i) {
      const newNode = newNodesLookup[this.nodes[i]._id];
      if (newNode === undefined) {
        continue;
      }

      this.nodes[i]._cached_node = newNodesLookup[this.nodes[i]._id]._cached_node;
    }

    this.reactFlowInstance.setNodes(this.nodes.map(node => this.nodeToFlowNode(node)));

    this.setState({
      nodes: this.nodes,
    });
  }

  clearCacheNodes() {
    if (!this.nodes) {
       return;
    }
    let i;
    for (i = 0; i < this.nodes.length; ++i) {
      this.nodes[i]._cached_node = null;
    }
    this.setState({
      nodes: this.nodes,
    });
  }

  onOutputClick(nid, outputName, displayRaw) {
    if (!this.node_lookup.hasOwnProperty(nid)) {
      console.error("Cannot find node with id " + nid);
      return;
    }
    const node = this.node_lookup[nid];
    const outputs = node._cached_node ? node._cached_node.outputs : node.outputs;
    const output = outputs.filter(item => item.name === outputName)[0];
    if (output.values.length > 0) {
      this.handlePreview({
        title: output.name,
        file_type: output.file_type,
        values: output.values,
        download_name: output.name,
        display_raw: displayRaw,
      });
    } else {
      console.log("Resource is not ready yet");
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

    copyPressed: () => {
      const nodesToCopy = [...this.selectedNodeIds].map(
          nid => JSON.parse(JSON.stringify(this.node_lookup[nid]))
      ).filter((node) => node && node.node_running_status !== NODE_RUNNING_STATUS.SPECIAL);
      const edgesToCopy = [];

      for (const edge of this.reactFlowInstance.getEdges()) {
          if (this.selectedNodeIds.has(edge.source) || this.selectedNodeIds.has(edge.target)) {
              edgesToCopy.push(edge);
          }
      }

      for (var node of nodesToCopy) {
          for (var input of node.inputs) {
              input.input_references = [];
          }

          if (node.node_running_status !== NODE_RUNNING_STATUS.STATIC) {
              for (var output of node.outputs) {
                  output.values = []; // clear outputs
              }
          }

          if (node.node_running_status !== NODE_RUNNING_STATUS.STATIC) {
            node.node_running_status = NODE_RUNNING_STATUS.CREATED;
          }
          node._cached_node = null;
      }

      const copyObject = {
        nodes: nodesToCopy,
        edges: edgesToCopy,
      };
      console.log("Copy", copyObject);

      storeToClipboard(copyObject);
    },
    pastePressed: () => {
      console.log("PASTE");
      if (!this.state.editable) {
          console.log("Could not paste into read only graph");
          return;
      }

      const copyBody = loadFromClipboard();
      console.log(copyBody);
      if (!copyBody) {
        return;
      }

      const changesToApply = [];
      const oldNodeIdToNewId = {}
      this.selectedNodeIds.clear();

      for (const node of copyBody.nodes) {
          const newNodeId = new ObjectID().toString();
          oldNodeIdToNewId[node._id] = newNodeId;
          node._id = newNodeId;
          this.selectedNodeIds.add(node._id);

          const position = {
              x: node.x + 20,
              y: node.y + 20,
          };

          changesToApply.push({
              changeType: ChangeType.DROP_NODE,
              node: node,
              replaceNodeId: false,
              replaceOriginalNode: false,
              position: position,
          });
      }

      for (const edge of copyBody.edges) {
          var source = oldNodeIdToNewId.hasOwnProperty(edge.source) ? oldNodeIdToNewId[edge.source] : edge.source;
          var target = oldNodeIdToNewId.hasOwnProperty(edge.target) ? oldNodeIdToNewId[edge.target] : edge.target;

          changesToApply.push({
              changeType: ChangeType.CREATE_EDGE,
              connection: {source: source, sourceHandle: edge.sourceHandle, target: target, targetHandle: edge.targetHandle},
              pushToReactflow: true,
          });
      }

      this.applyChanges(changesToApply);

      this.reactFlowInstance.setNodes(
          (nds) => {
              for (var ii = 0; ii < nds.length; ++ii) {
                  nds[ii].selected = this.selectedNodeIds.has(nds[ii].id)
              }
              return nds;
          }
      )
    },
  };

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

  nodeToFlowNode(node) {
      return {
        id: node._id,
        type: "operation",
        position: {x: node.x, y: node.y},
        data: {
            node: node,
            onOutputClick: (outputName, displayRaw) => this.onOutputClick(node._id, outputName, displayRaw),
        },
        selected: this.selectedNodeIds.has(node._id),
      };
  }

  onNodesChange(nodeChanges) {
      var eventsToPass = [];
      for (var ii = 0; ii < nodeChanges.length; ++ii) {
          const nodeChange = nodeChanges[ii];

          switch (nodeChange.type) {
              case "remove":
                  eventsToPass.push({changeType: ChangeType.DELETE_NODE, id: nodeChange.id});
                  break;
              case "select":
                  if (nodeChange.selected) {
                      eventsToPass.push({changeType: ChangeType.SELECT_NODE, id: nodeChange.id})
                  } else {
                      eventsToPass.push({changeType: ChangeType.DESELECT_NODE, id: nodeChange.id});
                  }
                  break;
          }
      }
      this.applyChanges(eventsToPass);
  }

  onDragOver(event) {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
  }

  onDrop(event) {
    event.preventDefault();
    const obj = event.dataTransfer.getData('application/reactflow')
    //addNodes

    const reactFlowBounds = this.reactFlowWrapper.current.getBoundingClientRect();
    const node = JSON.parse(obj);

    const position = this.reactFlowInstance.project({
      x: event.clientX - reactFlowBounds.left,
      y: event.clientY - reactFlowBounds.top,
    });
    this.applyChanges([{
        changeType: ChangeType.DROP_NODE,
        node: node,
        replaceNodeId: true,
        replaceOriginalNode: true,
        position: position,
    }]);
  }

  onEdgesDelete(edges) {
    this.applyChanges(
        edges.map(edge => ({changeType: ChangeType.DELETE_EDGE, edge: edge}))
    );
  }

  onConnect(connection) {
    this.applyChanges([{changeType: ChangeType.CREATE_EDGE, connection: connection, pushToReactflow: false}]);
  }

  onNodeDrag(event, node, nodes) {
      nodes.map(n => {this.node_lookup[n.id].x = n.position.x; this.node_lookup[n.id].y = n.position.y; });
  }

  onNodeDragStop(event, node, nodes) {
      this.applyChanges(
          nodes.map(node => ({changeType: ChangeType.MOVE_NODE, node: node}))
      );
  }

  applyChanges(changes) {
      for (var ii = 0; ii < changes.length; ++ii) {
        const change = changes[ii];
        switch (change.changeType) {
          case ChangeType.DELETE_EDGE:
            this.applyDeleteEdge(change.edge);
            break;
          case ChangeType.CREATE_EDGE:
            this.applyCreateEdge(change.connection, change.pushToReactflow);
            break;
          case ChangeType.MOVE_NODE:
            this.applyMoveNode(change.node);
            break;
          case ChangeType.DELETE_NODE:
            this.applyDeleteNode(change.id);
            break
          case ChangeType.DROP_NODE:
            this.applyDropNode(change.node, change.replaceNodeId, change.replaceOriginalNode, change.position);
            break
          case ChangeType.SELECT_NODE:
            this.applyNodeSelect(change.id);
            break;
          case ChangeType.DESELECT_NODE:
            this.applyNodeDeselect(change.id);
            break;
          default:
            console.error(`Unknown ChangeType: ${change.changeType}`);
        }
      }
      if (changes.length > 0) {
          this.props.onNodeChange(this.graph_node);
          console.log("this.graph_node", this.graph_node);
      }
  }

  applyDeleteEdge(edge) {
      const to_node = this.node_lookup[edge.target];
      const input = to_node.inputs.find((input_) => {
        return input_.name === edge.targetHandle;
      });
      input.input_references = input.input_references.filter((value) => {
        return !(value.output_id === edge.sourceHandle && value.node_id === edge.source);
      });
  }

  applyCreateEdge(connection, pushToReactflow) {
      const from_node = this.node_lookup[connection.source];
      if (!from_node) {
          console.log(`Source node ${connection.source} not found` );
          return;
      }
      const node_output = from_node.outputs.find(
        (node_output_) => {
          return node_output_.name === connection.sourceHandle;
        }
      );

      const to_node = this.node_lookup[connection.target];
      if (!to_node) {
          console.log(`Target node ${connection.target} not found` );
          return;
      }
      const node_input = to_node.inputs.find(
        (node_input_) => {
          return node_input_.name === connection.targetHandle;
        }
      );

      if (!node_input) {
        throw new Error("Node input with name '" + to_pin + "' not found");
      }
      if (!node_output) {
        throw new Error("Node input with name '" + from_pin + "' not found");
      }

      // check if we could add the edge
      if (node_input.is_array || node_input.input_references.length == 0) {
          node_input.input_references.push({
            "node_id": connection.source,
            "output_id": connection.sourceHandle,
          });

          if (pushToReactflow) {
              // TODO check if needed to insert the edge
              this.reactFlowInstance.addEdges({
                  id: `${connection.source}-${connection.sourceHandle}-${connection.target}-${connection.targetHandle}`,
                  source: connection.source,
                  target: connection.target,
                  sourceHandle: connection.sourceHandle,
                  targetHandle: connection.targetHandle,
                  interactionWidth: 6,
              });
          }
      }
  }

  applyMoveNode(node) {
      const node_to_apply = this.node_lookup[node.id];
      node_to_apply.x = node.position.x;
      node_to_apply.y = node.position.y;
  }

  applyDeleteNode(node_id) {
      if (this.node_lookup[node_id].node_running_status === NODE_RUNNING_STATUS.SPECIAL) {
        console.error('Cannot remove special node');
        return;
      }

      this.nodes.splice(
          this.nodes.map(node => node._id === node_id).indexOf(true),     // simply indexOf does not work!
          1
      );

      this.applyNodeDeselect(node_id);
      delete this.node_lookup[node_id];
  }

  applyDropNode(node, replaceNodeId, replaceOriginalNode, position) {
      if (replaceOriginalNode) {
        node.original_node_id = node._id;
      }
      if (replaceNodeId) {
          node._id = new ObjectID().toString();
      }
      node.parent_node_id = null;
      node.successor_node_id = null;
      node.x = position.x;
      node.y = position.y;

      const flowNode = this.nodeToFlowNode(node);

      this.nodes.push(node)
      this.node_lookup[node._id] = node;
      this.reactFlowInstance.setNodes((nds) => nds.concat(flowNode));
  }

  applyNodeSelect(node_id) {
      const prevSize = this.selectedNodeIds.size;
      this.selectedNodeIds.add(node_id);
      const newSize = this.selectedNodeIds.size;
      if (prevSize === newSize) {
          return
      }
      this.applySelection();
  }

  applyNodeDeselect(node_id) {
      const prevSize = this.selectedNodeIds.size;
      this.selectedNodeIds.delete(node_id);
      const newSize = this.selectedNodeIds.size;
      if (prevSize === newSize) {
          return
      }
      this.applySelection();
  }

  applySelection() {
      if (this.selectedNodeIds.size === 1) {
        const [nid] = this.selectedNodeIds;
        const node = this.node_lookup[nid];
        if (node) {
          this.propertiesBar.setNodeData(node);
        }
      } else if (this.selectedNodeIds.size > 1) {
        this.propertiesBar.setNodeDataArr([...this.selectedNodeIds].map((nid) => this.node_lookup[nid]));
      } else {
        this.propertiesBar.setNodeData(this.graph_node);
      }
  }

  render() {
    return (
    <HotKeys className="GraphNode"
             handlers={this.keyHandlers} keyMap={KEY_MAP}
    >
      <ReactFlowProvider>
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
            values={this.state.previewData.values}
            display_raw={this.state.previewData.display_raw}
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

        <div
            style={{ height: '100%' }}
            className="graph-flow"
            ref={this.reactFlowWrapper}
            //{...register("reactFlowWrapper")}
            >
          <ReactFlow
            defaultNodes={this.state.flowNodes}
            nodeTypes={nodeTypes}
            defaultEdges={this.state.flowEdges}
            ref={this.reactFlowInstance}
            onNodesChange={nodeChanges => this.onNodesChange(nodeChanges)}
            onEdgesDelete={edges => this.onEdgesDelete(edges)}
            onEdgeUpdateEnd={(event, edge, handleType) => console.log("onEdgeUpdateEnd", event, edge, handleType)}
            onConnect={connection => this.onConnect(connection)}
            onNodeDrag={(event, node, nodes) => this.onNodeDrag(event, node, nodes)}
            onNodeDragStop={(event, node, nodes) => this.onNodeDragStop(event, node, nodes)}
            onInit={reactFlowInstance => {this.reactFlowInstance = reactFlowInstance; this.loadGraphFromJson(this.props.node);}}
            defaultEdgeOptions={{
                style:{strokeWidth: "5px"},
            }}
            onDrop={event => this.onDrop(event)}
            onDragOver={event => this.onDragOver(event)}
            proOptions={proOptions}
            fitView
            >
            <Background />
            <ControlsStyled/>
            <MiniMap
                style={minimapStyle}
                zoomable pannable
                 />
          </ReactFlow>
        </div>

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
      </ReactFlowProvider>
    </HotKeys>
    );
  }
}

export default Graph;
