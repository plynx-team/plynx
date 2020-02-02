/* eslint max-lines: 0 */
import React, { Component } from 'react';
import PropTypes from 'prop-types';
import queryString from 'query-string';
import ReactNodeGraph from '../3rd_party/react_node_graph';
import { typesValid } from '../../graphValidation';
import cookie from 'react-cookies';
import NodesBar from './NodesBar';
import PreviewDialog from '../Dialogs/PreviewDialog';
import PropertiesBar from './PropertiesBar';
import withDragDropContext from './withDragDropContext';
import DemoScreen from '../DemoScreen';
import FileDialog from '../Dialogs/FileDialog';
import CodeDialog from '../Dialogs/CodeDialog';
import {PluginsProvider} from '../../contexts';
import {ObjectID} from 'bson';
import {HotKeys} from 'react-hotkeys';
import {
  ACTION,
  VALIDATION_CODES,
  GRAPH_RUNNING_STATUS,
  NODE_RUNNING_STATUS,
  SPECIAL_TYPE_NAMES,
  OPERATIONS,
  KEY_MAP,
} from '../../constants';
import { API_ENDPOINT } from '../../configConsts';
import { storeToClipboard, loadFromClipboard } from '../../utils';

import "./gridtile.png";
import "./node.css";
import "./style.css";

function parameterIsSpecial(parameter) {
  return SPECIAL_TYPE_NAMES.indexOf(parameter.parameter_type) > -1 && parameter.widget !== null;
}

class Graph extends Component {
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
    this.graph_node = {};
    this.node_lookup = {};
    this.block_lookup = {};
    this.connections = [];
    document.title = "Graph";

    this.state = {
      blocks: [],
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

    this.loadGraphFromJson(this.props.node)
  }

  loadGraphFromJson(data) {
    this.graph_node = data;
    document.title = this.graph_node.title + " - Graph - PLynx";
    console.log(this.graph_node);
    this.connections = [];
    this.blocks = [];
    const ts = new ObjectID().toString();
    for (let i = 0; i < this.graph_node.parameters.length; ++i) {
        if (this.graph_node.parameters[i].name === '_nodes') {
            this.nodes = this.graph_node.parameters[i].value.value;
            break
        }
    }

    for (let i = 0; i < this.nodes.length; ++i) {
      const node = this.nodes[i];
      const inputs = [];
      const outputs = [];
      const specialParameterNames = [];
      let j = 0;

      if (node.inputs) {
        for (j = 0; j < node.inputs.length; ++j) {
          inputs.push({
            name: node.inputs[j].name,
            file_types: node.inputs[j].file_types
          });
          for (let k = 0; k < node.inputs[j].values.length; ++k) {
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

      if (!node.hasOwnProperty("x")) {
        node.x = Math.floor(Math.random() * 800) + 1;
      }
      if (!node.hasOwnProperty("y")) {
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
          "in": inputs,
          "out": outputs
        },
        "nodeRunningStatus": node.node_running_status,
        "nodeStatus": node.node_status,
        "specialParameterNames": specialParameterNames,
        "_ts": ts,
      });
      this.node_lookup[node._id] = node;
      this.block_lookup[node._id] = this.blocks[this.blocks.length - 1];
    }

    /*
    const nid = queryString.parse(this.props.location.search).nid;
    */
    const nid = null;

    this.setState({
      "blocks": this.blocks,
      "connections": this.connections,
      "graph": this.graph_node,
      "editable": this.graph_node.node_running_status.toUpperCase() === GRAPH_RUNNING_STATUS.CREATED,

    }, () => {
      if (nid) {
        this.mainGraph.getDecoratedComponentInstance().selectBlocks([nid]);
      }
    });
  }

  updateGraphFromJson(newGraph) {
    console.log("update");
    let i = 0;
    let block = null;

    const blocks_lookup_index = {};
    for (i = 0; i < this.blocks.length; ++i) {
      block = this.blocks[i];
      blocks_lookup_index[block.nid] = i;
    }

    let newNodes = newGraph.parameters.filter((p) => p.name === '_nodes')[0].value.value;

    for (i = 0; i < newNodes.length; ++i) {
      const node = newNodes[i];
      block = this.blocks[blocks_lookup_index[node._id]];
      block.nodeRunningStatus = node.node_running_status;
      block.nodeStatus = node.node_status;
      block.cacheUrl = node.cache_url;
      this.node_lookup[node._id] = newNodes[i];
      this.block_lookup[node._id] = block;
    }

    this.graph_node = newGraph;

    this.setState({
      "blocks": this.blocks,
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
      from_block: from_nid,
      from: from_pin,
      to_block: to_nid,
      to: to_pin
    });

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

    this.setState({connections: this.connections});

    this.props.onNodeChange(this.graph_node);
  }

  onRemoveConnector(connector) {
    let connections = this.connections;
    connections = connections.filter((connection) => {
      return connection !== connector;
    });

    const to_node = this.node_lookup[connector.to_block];
    const input = to_node.inputs.filter((input_) => {
      return input_.name === connector.to;
    })[0];
    input.values = input.values.filter((value) => {
      return !(value.output_id === connector.from && value.node_id === connector.from_block);
    });

    this.connections = connections;
    this.setState({connections: connections});

    this.props.onNodeChange(this.graph_node);
  }

  onRemoveBlock(nid) {
    this.nodes.splice(this.nodes.indexOf(node => node._id == nid));
    delete this.node_lookup[nid];
    this.blocks = this.blocks.filter((block) => {
      return block.nid !== nid;
    });

    this.setState({blocks: this.blocks});

    this.props.onNodeChange(this.graph_node);
  }

  onCopyBlock(copyList, offset) {
    const nodes = copyList.nids.map(nid => this.node_lookup[nid]);
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
        let index = -1;
        for (let jj = 0; jj < to_node.inputs.length; ++jj) {
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

    if (nids.length === 1) {
      const nid = nids[0];
      const node = this.node_lookup[nid];
      if (node) {
        this.propertiesBar.setNodeData(node);

        if (this.block_lookup[nid].highlight) {
          this.block_lookup[nid].highlight = false;
          this.setState({
            "blocks": this.blocks
          });
        }
      }
    } else if (nids.length > 1) {
      this.propertiesBar.setNodeDataArr(nids.map((nid) => this.node_lookup[nid]));
    } else {
      this.propertiesBar.setNodeData(this.graph_node);
    }
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
    this.postGraph(this.graph, false, ACTION.REARRANGE);
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
    let j = 0;
    for (let i = 0; i < this.graph.nodes.length; ++i) {
      const node = this.graph.nodes[i];
      if (node.node_running_status !== NODE_RUNNING_STATUS.STATIC) {
        node.node_running_status = NODE_RUNNING_STATUS.CREATED;
      }
      if (node.inputs) {
        for (j = 0; j < node.inputs.length; ++j) {
          const input_values = node.inputs[j].values;
          for (let k = 0; k < input_values.length; ++k) {
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

  handleParameterChanged(node_ids, name, value) {
    for (var ii = 0; ii < node_ids.length; ++ii) {
        var node_id = node_ids[ii];
        var node;
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
            var inName = name.substring(1, name.length).toLowerCase()
            const block = this.block_lookup[node_id];
            node[inName] = value;
            if (block) { // the case of graph itself
                block[inName] = value;
            } else {
                // using for node, it is hard to update descriptions
                this.setState({graph: this.graph_node})
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

  handleDrop(blockObjArg, replaceParentNode) {
    const blockObj = JSON.parse(JSON.stringify(blockObjArg)); // copy
    const node = blockObj.nodeContent;
    const inputs = [];
    const outputs = [];
    const specialParameterNames = [];

    let i = 0;

    if (replaceParentNode) {
      node.original_node_id = node._id;
    }
    node.parent_node_id = null;
    node.successor_node_id = null;
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
    node.x = Math.max(blockObj.mousePos.x - 340, 0);
    node.y = Math.max(blockObj.mousePos.y - 80, 0);

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
          "in": inputs,
          "out": outputs
        },
        "nodeRunningStatus": node.node_running_status,
        "nodeStatus": node.node_status,
        "specialParameterNames": specialParameterNames,
      });

    this.node_lookup[node._id] = node;
    this.block_lookup[node._id] = this.blocks[this.blocks.length - 1];

    this.nodes.push(node);
    console.log("node", node);

    this.setState({
      blocks: this.blocks,
      connections: this.connections,
    });

    this.props.onNodeChange(this.graph_node);

    return node._id;
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

  render() {
    const demoPreview = !!cookie.load('demoPreview');

    return (
    <HotKeys className="GraphNode"
             handlers={this.keyHandlers} keyMap={KEY_MAP}
    >
      <PluginsProvider value={this.props.plugins_dict}>
        { demoPreview &&
          <DemoScreen onApprove={() => this.handleApprove()} onClose={() => {
            cookie.remove('demoPreview', { path: '/' });
            this.forceUpdate();
          }} />
        }
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

        {/* Visible and flex layout blocks */}
        {this.state.editable && <NodesBar/> }

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
        />
        }
      </PluginsProvider>
    </HotKeys>
    );
  }
}


export default withDragDropContext(Graph);
