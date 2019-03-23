import React, { Component } from 'react';
import queryString from 'query-string';
import ReactNodeGraph from '../3rd_party/react_node_graph';
import AlertContainer from 'react-alert-es6';
import { PLynxApi } from '../../API.js';
import { typesValid } from '../../graphValidation.js';
import { DragDropContextProvider } from 'react-dnd'
import TouchBackend from 'react-dnd-touch-backend';
import HTML5Backend from 'react-dnd-html5-backend'
import cookie from 'react-cookies'
import { isMobile } from "react-device-detect";
import NodesBar from './NodesBar.js'
import PreviewDialog from '../Dialogs/PreviewDialog.js'
import PropertiesBar from './PropertiesBar.js'
import Controls from './Controls.js'
import LoadingScreen from '../LoadingScreen.js'
import DemoScreen from '../DemoScreen.js'
import FileDialog from '../Dialogs/FileDialog.js'
import CodeDialog from '../Dialogs/CodeDialog.js'
import { ObjectID } from 'bson';
import {HotKeys} from 'react-hotkeys';
import {
  ACTION,
  RESPONCE_STATUS,
  ALERT_OPTIONS,
  VALIDATION_CODES,
  GRAPH_RUNNING_STATUS,
  NODE_RUNNING_STATUS,
  SPECIAL_TYPE_NAMES,
  OPERATIONS,
  KEY_MAP,
} from '../../constants.js';
import { API_ENDPOINT } from '../../configConsts'
import { storeToClipboard, loadFromClipboard } from '../../utils.js';

import "./gridtile.png"
import "./node.css"
import "./style.css"

function parameterIsSpecial(parameter) {
  return SPECIAL_TYPE_NAMES.indexOf(parameter.parameter_type) > -1 && parameter.widget != null;
}

export class Graph extends Component {

  constructor(props) {
    super(props);
    this.graph = {};
    this.node_lookup = {}
    this.block_lookup = {}
    this.connections = []
    document.title = "Graph";

    this.state = {
      blocks: [],
      connections: [],
      graphId: null,
      editable: false,
      loading: true,
      title: "",
      description: "",
      graphRunningStatus: null,
      previewData: null,
      generatedCode: "",
    };

    var token = cookie.load('refresh_token');
    // TODO remove after demo
    if (token === 'Not assigned') {
      token = cookie.load('access_token');
    }

    this.generatedCodeHeader =
`#!/usr/bin/env python
from plynx.api import Operation, File, Graph, Client

TOKEN = '` + token +`'
ENDPOINT = '` + API_ENDPOINT + `'


`
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async componentDidMount() {
    // Loading

    var self = this;
    var loading = true;
    var graph_id = this.props.match.params.graph_id.replace(/\$+$/, '');
    var sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    var loadGraph = function (response) {
      self.loadGraphFromJson(response.data.data);
      console.log(graph_id);
      if (graph_id === 'new') {
        self.props.history.replace("/graphs/" + self.graph._id)
      }
      loading = false;
    };

    var handleError = function (error) {
      console.error(error);
      console.error('-----------');
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
    }

    while (loading) {
      await PLynxApi.endpoints.graphs.getOne({ id: graph_id})
      .then(loadGraph)
      .catch(handleError);
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

  loadGraphFromJson(data) {
    this.graph = data;
    document.title = this.graph.title + " - Graph - PLynx";
    console.log(this.graph);
    this.connections = [];
    this.blocks = [];
    var ts = new ObjectID().toString();

    for (var i = 0; i < this.graph.nodes.length; ++i) {
        var node = this.graph.nodes[i];
        var inputs = [];
        var outputs = [];
        var specialParameterNames = [];

        if (node.inputs) {
          for (var j = 0; j < node.inputs.length; ++j) {
            inputs.push({
              name: node.inputs[j].name,
              file_types: node.inputs[j].file_types
            });
            for (var k = 0; k < node.inputs[j].values.length; ++k) {
              this.connections.push({
                "from_block": node.inputs[j].values[k].node_id,
                "from": node.inputs[j].values[k].output_id,
                "to_block": node._id,
                "to": node.inputs[j].name}
              );
            }
          }
        }
        for (j = 0; j < node.outputs.length; ++j) {
          outputs.push({
            name: node.outputs[j].name,
            file_type: node.outputs[j].file_type
          });
        }

        for (j = 0; j < node.parameters.length; ++j) {
          if (parameterIsSpecial(node.parameters[j])) {
            specialParameterNames.push(node.parameters[j].name);
          }
        }

        if(!node.hasOwnProperty("x")) {
          node.x = Math.floor(Math.random() * 800) + 1;
        }
        if(!node.hasOwnProperty("y")) {
          node.y = Math.floor(Math.random() * 400) + 1;
        }

        this.blocks.push({
            "nid": node._id,
            "title": node.title,
            "description": node.description,
            "cacheUrl": node.cache_url,
            "x": node.x,
            "y": node.y,
            "fields":
            {
              "in":inputs,
              "out":outputs
            },
            "nodeRunningStatus": node.node_running_status,
            "nodeStatus": node.node_status,
            "specialParameterNames": specialParameterNames,
            "_ts": ts,
          });
          this.node_lookup[node._id] = node;
          this.block_lookup[node._id] = this.blocks[this.blocks.length - 1];
    }

    var nid = queryString.parse(this.props.location.search).nid;
    if (nid) {
      this.block_lookup[nid].highlight = true;
    }

    this.setState({
      "blocks": this.blocks,
      "connections": this.connections,
      "graphId": this.graph._id,
      "editable": this.graph.graph_running_status.toUpperCase() === GRAPH_RUNNING_STATUS.CREATED,
      "loading": false,
      "title": this.graph.title,
      "description": this.graph.description,
      "graphRunningStatus": this.graph.graph_running_status,
    });

    var st = this.graph.graph_running_status.toUpperCase();
    if (st === 'READY' || st === GRAPH_RUNNING_STATUS.RUNNING || st === GRAPH_RUNNING_STATUS.FAILED_WAITING) {
      this.timeout = setTimeout(() => this.checkGraphStatus(), 1000);
    }
  }

  updateGraphFromJson(newGraph) {
    console.log("update");

    var blocks_lookup_index = {};
    for (var i = 0; i < this.blocks.length; ++i) {
      var block = this.blocks[i];
      blocks_lookup_index[block.nid] = i;
    }

    for (i = 0; i < newGraph.nodes.length; ++i) {
      var node = this.graph.nodes[i];
      block = this.blocks[blocks_lookup_index[node._id]];
      block.nodeRunningStatus = node.node_running_status;
      block.nodeStatus = node.node_status;
      block.cacheUrl = node.cache_url;
      this.node_lookup[node._id] = newGraph.nodes[i];
      this.block_lookup[node._id] = block;
    }

    this.setState({
      "blocks": this.blocks,
      "loading": false,
      "graphRunningStatus": newGraph.graph_running_status,
    });

    var st = this.graph.graph_running_status.toUpperCase();
    if (st === 'READY' || st === GRAPH_RUNNING_STATUS.RUNNING || st === GRAPH_RUNNING_STATUS.FAILED_WAITING) {
      this.timeout = setTimeout(() => this.checkGraphStatus(), 1000);
    }

    this.graph = newGraph;
  }

  componentWillUnmount() {
    if (this.timeout) {
      clearTimeout(this.timeout);
    }
  }

  checkGraphStatus() {
    var self = this;
    var graph_id =  self.graph._id;
    PLynxApi.endpoints.graphs.getOne({ id: graph_id})
    .then(function (response) {
      self.updateGraphFromJson(response.data.data);
    })
    .catch(function (error) {
      console.log(error);
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then(function (isSuccessfull) {
          if (isSuccessfull) {
            self.timeout = setTimeout(() => self.checkGraphStatus(), 1000);
          } else {
            console.error("Could not refresh token");
            self.showAlert('Failed to authenticate', 'failed');
          }
        });
      }
    });
  }

  onNewConnector(from_nid, from_pin, to_nid, to_pin) {
    var from_node = this.node_lookup[from_nid];
    var node_output = from_node.outputs.find(
      function(node_output) {
        return node_output.name === from_pin
      }
    );

    var to_node = this.node_lookup[to_nid];
    var node_input = to_node.inputs.find(
      function(node_input) {
        return node_input.name === to_pin
      }
    );

    if (!node_input) {
      throw new Error("Node input with name '" + to_pin + "' not found");
    }
    if (!node_output) {
      throw new Error("Node input with name '" + from_pin + "' not found");
    }

    if (node_input.max_count > 0 && node_input.values.length >= node_input.max_count) {
       this.showAlert("No more slots for new connections left", 'warning');
       return;
    }

    if (!typesValid(node_output, node_input)) {
      this.showAlert("Incompatible types", 'warning');
      return;
    }

    if (node_input.values.filter(
        (a) => a.node_id === from_nid && a.output_id === from_pin).length > 0) {
      this.showAlert("Connection already exists", 'warning');
      return;
    }

    this.connections.push({
      from_block : from_nid,
      from : from_pin,
      to_block : to_nid,
      to : to_pin
    })

    node_input.values.push({
      "node_id": from_nid,
      "output_id": from_pin
    });

    if (this.block_lookup[to_nid].highlight) {
      this.block_lookup[to_nid].highlight = false;
      this.setState({
        "blocks": this.blocks
      });
    }

    console.log(this.graph);

    this.setState({connections: this.connections})
  }

  onRemoveConnector(connector) {
    var connections = this.connections;
    connections = connections.filter((connection) => {
      return connection !== connector
    });

    var to_node = this.node_lookup[connector.to_block];
    var input = to_node.inputs.filter((input) => {
      return input.name === connector.to;
    })[0];
    input.values = input.values.filter((value) => {
      return !(value.output_id === connector.from && value.node_id === connector.from_block);
    })

    this.connections = connections;
    this.setState({connections: connections})
  }

  onRemoveBlock(nid) {
    this.graph.nodes = this.graph.nodes.filter((node) => {
      return node._id !== nid;
    });
    delete this.node_lookup[nid];
    this.blocks = this.blocks.filter((block) => {
      return block.nid !== nid;
    });

    this.setState({blocks: this.blocks});
  }

  onCopyBlock(copyList) {
    var nodes = copyList.nids.map(nid => this.node_lookup[nid]);
    var copyObject = {
      nodes: nodes,
      connectors: copyList.connectors,
    };
    console.log(copyList.nids, copyObject);

    storeToClipboard(copyObject);
  }

  onPasteBlock() {
    var copyBody = loadFromClipboard();
    var nidOldToNew = {};
    if (!copyBody) {
      return;
    }
    var ii;
    var pastedBlockIds = [];
    this.mainGraph.decoratedComponentInstance.deselectAll(false);
    for (ii = 0; ii < copyBody.nodes.length; ++ii) {
      var blockJson = copyBody.nodes[ii];
      var block_id = this.handleDrop(
        {
          nodeContent: blockJson,
          mousePos: {
            x: blockJson.x + 380,
            y: blockJson.y + 120,
          },
        },
        false);
      nidOldToNew[blockJson._id] = block_id;
      pastedBlockIds.push(block_id);
    }
    for (ii = 0; ii < copyBody.connectors.length; ++ii) {
      let connector = copyBody.connectors[ii];
      var { to_block, from_block } = connector;
      if (nidOldToNew.hasOwnProperty(to_block)) {
        to_block = nidOldToNew[to_block];
      }
      if (nidOldToNew.hasOwnProperty(from_block)) {
        from_block = nidOldToNew[from_block];
      }
      var from_node = this.node_lookup[from_block]
      var to_node = this.node_lookup[to_block]
      if (from_node && to_node) {
        var index = -1;
        for (var jj = 0; jj < to_node.inputs.length; ++jj) {
          if (to_node.inputs[jj].name === connector.to) {
            index = jj;
            break;
          }
        }
        if (index < 0) {
          throw new Error("Index not found for " + connector.to);
        }
        if (to_node.inputs[index].max_count > 0 && to_node.inputs[index].values.length >= to_node.inputs[index].max_count) {
          continue;
        }

        to_node.inputs[index].values.push({
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
    this.mainGraph.decoratedComponentInstance.selectBlocks(pastedBlockIds);
    this.setState({
      nodes: this.nodes,
      connections: this.connections,
    });
  }

  onOutputClick(nid, outputIndex) {
    if (!this.node_lookup.hasOwnProperty(nid)) {
      console.error("Cannot find node with id " + nid);
      return;
    }
    let node = this.node_lookup[nid];
    let output = node.outputs[outputIndex];
    if (output.resource_id) {
      this.handlePreview({
        title: output.name,
        file_type: output.file_type,
        resource_id: output.resource_id,
        download_name: output.name,
    });
    } else {
      console.log("Resource is not ready yet");
    }
  }

  onSpecialParameterClick (nid, specialParameterIndex) {
    if (!this.node_lookup.hasOwnProperty(nid)) {
      console.error("Cannot find node with id " + nid);
      return;
    }
    var node = this.node_lookup[nid];
    var idx = 0;
    for (var i = 0; i < node.parameters.length; ++i) {
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
    var node = this.node_lookup[nid];
    node.x = pos.left;
    node.y = pos.top;
  }

  handleBlocksSelect(nids) {
    console.log('blocks selected : ' + nids);

    if (nids.length === 1) {
      let nid = nids[0];
      var node = this.node_lookup[nid];
      if (node) {
        this.propertiesBar.setNodeData(
          this.graph._id,
          node._id,
          node.base_node_name,
          node.title,
          node.description,
          node.parameters,
          node.outputs,
          node.logs,
          node.parent_node,
        );

        if (this.block_lookup[nid].highlight) {
          this.block_lookup[nid].highlight = false;
          this.setState({
            "blocks": this.blocks
          });
        }
      }
    } else if (nids.length > 1) {
      this.propertiesBar.clearData();
    } else {
      this.handleAllBlocksDeselect();
    }
  }

  handleBlockDeselect(nid) {
    console.log('block deselected : ' + nid);

    if (this.block_lookup[nid].highlight) {
      this.block_lookup[nid].highlight = false;
      this.setState({
        "blocks": this.blocks
      });
    }
    // var node = this.node_lookup[nid];
    // this.propertiesBar.clearData();
  }

  handleAllBlocksDeselect() {
    console.log("Graph properties");
    this.propertiesBar.setGraphData(
      this.graph._id,
      "Graph",
      [
        {
          name: 'title',
          parameter_type: "str",
          value: this.state.title,
          widget: {
            alias: "Title"
          }
        },
        {
          name: 'description',
          parameter_type: "str",
          value: this.state.description,
          widget: {
            alias: "Description"
          }
        }
      ]
    );
  }

  handleSave() {
    console.log(this.graph);
    this.postGraph(this.graph, false, ACTION.SAVE);
  }

  handleValidate() {
    console.log(this.graph);
    this.postGraph(this.graph, false, ACTION.VALIDATE);
  }

  handleApprove() {
    console.log(this.graph);
    this.postGraph(this.graph, true, ACTION.APPROVE);
  }

  handleRearrange() {
    this.postGraph(this.graph, false, ACTION.AUTO_LAYOUT);
  }

  handleGenerateCode() {
    this.postGraph(this.graph, false, ACTION.GENERATE_CODE);
  }

  handleUpgradeNodes() {
    this.postGraph(this.graph, false, ACTION.UPGRADE_NODES);
  }

  handleClone() {
    this.graph.graph_running_status = GRAPH_RUNNING_STATUS.CREATED;
    this.graph._id = new ObjectID().toString();
    var j = 0;
    for(var i = 0; i < this.graph.nodes.length; ++i) {
      var node = this.graph.nodes[i];
      if (node.node_running_status !== NODE_RUNNING_STATUS.STATIC) {
        node.node_running_status = NODE_RUNNING_STATUS.CREATED;
      }
      if (node.inputs) {
        for (j = 0; j < node.inputs.length; ++j) {
          var input_values = node.inputs[j].values
          for (var k = 0; k < input_values.length; ++k) {
            input_values[k].resource_id = null;
          }
        }
      }
      if (node.logs) {
        for (j = 0; j < node.logs.length; ++j) {
          node.logs[j].resource_id = null;
        }
      }
      if (node.node_running_status !== NODE_RUNNING_STATUS.STATIC) {
        for (j = 0; j < node.outputs.length; ++j) {
          node.outputs[j].resource_id = null;
        }
      }
      node.cache_url = null;
    }
    this.setState({
      editable: true,
      graphId: this.graph._id,
      graphRunningStatus: this.graph.graph_running_status,
    });
    this.loadGraphFromJson(this.graph);
    this.props.history.push("/graphs/" + this.graph._id + '$');
  }

  handleCancel() {
    this.postGraph(this.graph, false, ACTION.CANCEL);
  }

  handleParameterChanged(nodeId, name, value) {
    if (nodeId) {
      var node = this.node_lookup[nodeId];
      var node_parameter = node.parameters.find(
        function(node_input) {
          return node_input.name === name
        }
      );
      if (node_parameter) {
        node_parameter.value = value;
      } else if (name === '_DESCRIPTION') {
        var block = this.block_lookup[nodeId];
        node.description = value;
        block.description = value;

        this.setState({
          blocks: this.blocks
        });

      } else {
        throw new Error("Parameter not found");
      }
    } else {
      this.setState({[name]: value});
      this.graph[name] = value;
    }
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
    })
  }

  handleCloseGeneratedCodeDialog() {
    this.setState({
      generatedCode: undefined,
    })
  }

  handleShowFile(nid) {
    this.setState({
      fileObj: this.node_lookup[nid]
    })
  }

  handleCloseFileDialog() {
    this.setState({
      fileObj: null
    });
  }

  closeAllDialogs() {
    this.handleClosePreview();
    this.handleCloseCodeDialog();
    this.handleCloseGeneratedCodeDialog();
    this.handleCloseFileDialog();
  }

  keyHandlers = {
    escPressed: () => {
      this.closeAllDialogs();
    },
  }

  handleDrop(blockObj, replaceParentNode) {
    blockObj = JSON.parse(JSON.stringify(blockObj)); // copy
    var node = blockObj.nodeContent;
    var inputs = [];
    var outputs = [];
    var specialParameterNames = [];

    var i = 0;

    if (replaceParentNode) {
      node.parent_node = node._id;
    }
    node._id = new ObjectID().toString();

    if (node.inputs) {
      for (i = 0; i < node.inputs.length; ++i) {
        inputs.push({
          name: node.inputs[i].name,
          file_types: node.inputs[i].file_types
        });
        node.inputs[i].values = []; // clear inputs on paste
      }
    }
    for (i = 0; i < node.outputs.length; ++i) {
      outputs.push({
        name: node.outputs[i].name,
        file_type: node.outputs[i].file_type
      });
    }
    for (i = 0; i < node.parameters.length; ++i) {
      if (parameterIsSpecial(node.parameters[i])) {
        specialParameterNames.push(node.parameters[i].name);
      }
    }
    node.x = blockObj.mousePos.x - 340;
    node.y = blockObj.mousePos.y - 80;


    console.log(node);
    if (OPERATIONS.indexOf(node.base_node_name) > -1) {
      node.node_running_status = NODE_RUNNING_STATUS.CREATED;
      node.cache_url = null;
    }

    this.blocks.push(
      {
        "nid": node._id,
        "title": node.title,
        "description": node.description,
        "cacheUrl": node.cache_url,
        "x": node.x,
        "y": node.y,
        "fields":
        {
          "in":inputs,
          "out":outputs
        },
        "nodeRunningStatus": node.node_running_status,
        "nodeStatus": node.node_status,
        "specialParameterNames": specialParameterNames,
      });

    this.node_lookup[node._id] = node;
    this.block_lookup[node._id] = this.blocks[this.blocks.length - 1];

    this.graph.nodes.push(node);
    console.log("node", node);

    this.setState({
      blocks: this.blocks,
      connections: this.connections,
    });

    return node._id;
  }

  postGraph(graph, reloadOnSuccess, action) {
    /*action might be in {'save', 'validate', 'approve', 'deprecate'}*/
    var self = this;
    self.setState({loading: true});
    PLynxApi.endpoints.graphs
    .create({
      body: {
        graph: graph,
        actions: [action]
      }
    })
    .then(function (response) {
      var data = response.data;
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
        } else if (action === ACTION.AUTO_LAYOUT) {
          self.loadGraphFromJson(data.graph);
        } else if (action === ACTION.UPGRADE_NODES) {
          self.loadGraphFromJson(data.graph);
          var message = "";
          if (data.upgraded_nodes_count > 0) {
            message = "Upgraded " + data.upgraded_nodes_count +
              (data.upgraded_nodes_count > 1 ? " Nodes" : " Node");
          }
          else {
            message = "No Nodes upgraded";
          }
          self.showAlert(message, 'success');
        } else if (action === ACTION.GENERATE_CODE) {
            self.setState({
              generatedCode: data.code
            })
        } else {
          self.showAlert("Success", 'success');
        }
        if (cookie.load('demoPreview')) {
          cookie.remove('demoPreview', { path: '/' });
        }
      } else if (data.status === RESPONCE_STATUS.VALIDATION_FAILED) {
        console.warn(data.message);
        // TODO smarter traverse
        self.showValidationError(data.validation_error)

        self.showAlert(data.message, 'failed');
      } else {
        console.warn(data.message);
        self.showAlert(data.message, 'failed');
      }
    })
    .catch(function (error) {
      console.log(error);
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
        self.showAlert('Failed to save the graph', 'failed');
      }
      self.setState({loading: false});
    });
  }

  showValidationError(validationError) {
    var children = validationError.children;
    for (var i = 0; i < children.length; ++i) {
      var child = children[i];
      var nodeId = null;
      var node = null;
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
      icon: <img src={"/alerts/" + type +".svg"} width="32" height="32" alt="alert"/>
    });
  }

  render() {
    var demoPreview = cookie.load('demoPreview') ? true : false;

    return (
      <DragDropContextProvider backend={isMobile ? TouchBackend : HTML5Backend}>
        <HotKeys className="GraphNode"
                 handlers={this.keyHandlers} keyMap={KEY_MAP}
        >
          <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
          { demoPreview &&
            <DemoScreen onApprove={() => this.handleApprove()} onClose={() => {cookie.remove('demoPreview', { path: '/' }); this.forceUpdate()}} />
          }
          {this.state.loading &&
            <LoadingScreen
            ></LoadingScreen>
          }
          <div className={'BackgroundLabels ' + (this.state.editable ? 'editable' : 'readonly')}>
            <div className="Title">{this.state.title}</div>
            <div className="Description">&ldquo;{this.state.description}&rdquo;</div>
          </div>
          {this.state.fileObj &&
            <FileDialog
              onClose={() => this.handleCloseFileDialog()}
              onDeprecate={(fileObj) => this.handleDeprecate(fileObj)}
              fileObj={this.state.fileObj}
              hideDeprecate={true}
              onPreview={(previewData) => this.handlePreview(previewData)}
              />
          }
          <Controls className="ControlButtons"
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
              readOnly={true}
            />
          }

          {/* Visible and flex layout blocks */}
          {this.state.editable && <NodesBar/> }

          <ReactNodeGraph className="MainGraph"
            ref={(child) => { this.mainGraph = child; }}
            data={this.state}
            graphId={this.state.graphId}
            editable={this.state.editable}
            onBlockMove={(nid, pos)=>this.onBlockMove(nid, pos)}
            onNewConnector={(n1,o,n2,i)=>this.onNewConnector(n1,o,n2,i)}
            onRemoveConnector={(connector)=>this.onRemoveConnector(connector)}
            onOutputClick={(nid, outputIndex)=>this.onOutputClick(nid, outputIndex)}
            onSpecialParameterClick={(nid, specialParameterIndex)=>this.onSpecialParameterClick(nid, specialParameterIndex)}
            onRemoveBlock={(nid)=>this.onRemoveBlock(nid)}
            onCopyBlock={(copyList)=>this.onCopyBlock(copyList)}
            onPasteBlock={()=>this.onPasteBlock()}
            onBlocksSelect={(nids) => {this.handleBlocksSelect(nids)}}
            onBlockDeselect={(nid) => {this.handleBlockDeselect(nid)}}
            onDrop={(nodeObj) => this.handleDrop(nodeObj, true)}
            onAllBlocksDeselect={() => this.handleAllBlocksDeselect()}
            onSavePressed={() => this.handleSave()}
            key={'graph' + this.state.graphId + this.state.loading}
          />

          <PropertiesBar className="PropertiesBar"
                        ref={(child) => { this.propertiesBar = child; }}
                        onParameterChanged={(nodeId, name, value) => this.handleParameterChanged(nodeId, name, value)}
                        editable={this.state.editable}
                        onPreview={(previewData) => this.handlePreview(previewData)}
                        graphId={this.graph._id}
                        graphTitle={this.state.title}
                        graphDescription={this.state.description}
                        key={"prop" + this.state.graphId + this.state.loading}
                        onFileShow={(nid) => this.handleShowFile(nid)}
          />
        </HotKeys>
      </DragDropContextProvider>
    );


  }
}
