import React from 'react';
import {HotKeys} from 'react-hotkeys';
import Block from './lib/Block';
import Spline from './lib/Spline';
import SVGComponent from './lib/SVGComponent';

import { ObjectID } from 'bson';
import PropTypes from 'prop-types';
import { DropTarget } from 'react-dnd';
import ItemTypes from '../../../DragAndDropsItemTypes';

import {computeOutOffsetByIndex, computeInOffsetByIndex} from './lib/util';
import { KEY_MAP, NODE_RUNNING_STATUS } from '../../../constants';

const STEP = 224;

const HEADER_HEIGHT = 23;
const DESCRIPTION_HEIGHT = 20;
const FOOTER_HEIGHT = 10;
const BORDERS_HEIGHT = 2;
const ITEM_HEIGHT = 20;
const COMMON_HEIGHT = HEADER_HEIGHT + DESCRIPTION_HEIGHT + FOOTER_HEIGHT + BORDERS_HEIGHT;


const getScrollOffset = () => {
  const el = document.getElementsByClassName('GraphRoot')[0];
  return {
    x: el.scrollLeft,
    y: el.scrollTop,
  };
};

const boxTarget = {
  drop(props, monitor, component) {     // eslint-disable-line no-unused-vars
    const graphProps = props;
    const blockObj = monitor.getItem();
    const mousePos = monitor.getClientOffset();

    if (graphProps.onDrop) {
      // Hack: use GraphRoot scroll position
      const offset = getScrollOffset();
      graphProps.onDrop({
        nodeContent: blockObj.nodeContent,
        mousePos: {
          x: mousePos.x + offset.x,
          y: mousePos.y + offset.y,
        },
      });
    }
    return { name: 'ReactBlockGraph' };
  },
};

function hashCode(str) { // java String#hashCode
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);      // eslint-disable-line no-bitwise
  }
  return hash;
}

function intToRGB(i) {
  const c = (i & 0x00FFFFFF)                              // eslint-disable-line no-bitwise
      .toString(16)
      .toUpperCase();

  return "00000".substring(0, 6 - c.length) + c;
}

class ReactBlockGraph extends React.Component {
  static propTypes = {
    data: PropTypes.object.isRequired,
    editable: PropTypes.bool.isRequired,
    graphId: PropTypes.string.isRequired,
    onAllBlocksDeselect: PropTypes.func.isRequired,
    onBlockMove: PropTypes.func.isRequired,
    onBlockStartMove: PropTypes.func.isRequired,
    onBlocksSelect: PropTypes.func.isRequired,
    onCopyBlock: PropTypes.func.isRequired,
    onNewConnector: PropTypes.func.isRequired,
    onOutputClick: PropTypes.func.isRequired,
    onPasteBlock: PropTypes.func.isRequired,
    onRemoveBlock: PropTypes.func.isRequired,
    onRemoveConnector: PropTypes.func.isRequired,
    onSavePressed: PropTypes.func.isRequired,
    onSpecialParameterClick: PropTypes.func.isRequired,
  }

  constructor(props) {
    super(props);

    this.selectedNIDs = [];

    this.state = {
      data: this.props.data,
      source: [],
      dragging: false,
      editable: this.props.editable,
      selectedNIDs: this.selectedNIDs,
      graphId: this.props.graphId,
    };

    this.onMouseMove = this.onMouseMove.bind(this);
    this.onMouseUp = this.onMouseUp.bind(this);
    this.commandPressed = false;
    this.recalcSize();
  }

  static propTypes = {
    connectDropTarget: PropTypes.func.isRequired,
    isOver: PropTypes.bool.isRequired,
    canDrop: PropTypes.bool.isRequired,
  }

  componentDidMount() {
    document.addEventListener('mousemove', this.onMouseMove);
    document.addEventListener('mouseup', this.onMouseUp);
  }

  componentWillUnmount() {
    document.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('mouseup', this.onMouseUp);
  }

  componentWillReceiveProps(nextProps) {
    this.setState({
      data: nextProps.data,
    });
  }

  recalcSize() {
    const nodes = this.state.data.nodes;
    let width = STEP * 10;
    let height = STEP * 8;
    for (let ii = 0; ii < nodes.length; ++ii) {
      width = Math.max(width, nodes[ii].x + 500);
      height = Math.max(height, nodes[ii].y + 500);
    }
    this.width = (Math.floor(width / STEP) * STEP) + 2;
    this.height = (Math.floor(height / STEP) * STEP) + 2;
  }

  onMouseDown(e) {
    if (this.preventDrawingBox) {
      return;
    }
    const {svgComponent: {refs: {svg}}} = this.refs;

    // Get svg element position to substract offset top and left
    const svgRect = svg.getBoundingClientRect();

    this.setState({
      firstMousePos: {
        x: e.pageX - svgRect.left,
        y: e.pageY - svgRect.top
      }
    });
  }

  onMouseUp() {
    if (this.state.firstMousePos && this.state.mousePos && !this.state.dragging) {
      const nodes = this.state.data.nodes;
      const minX = Math.min(this.state.firstMousePos.x, this.state.mousePos.x);
      const maxX = Math.max(this.state.firstMousePos.x, this.state.mousePos.x);
      const minY = Math.min(this.state.firstMousePos.y, this.state.mousePos.y);
      const maxY = Math.max(this.state.firstMousePos.y, this.state.mousePos.y);
      const nidsToSelect = [];
      for (let ii = 0; ii < nodes.length; ++ii) {
        const blockExtraHeight = ITEM_HEIGHT * Math.max(nodes[ii].inputs.length, nodes[ii].outputs.length);
        if (minX < nodes[ii].x + 180 && nodes[ii].x < maxX &&
            minY < nodes[ii].y + COMMON_HEIGHT + blockExtraHeight && nodes[ii].y < maxY) {
          nidsToSelect.push(nodes[ii]._id);
        }
      }

      if (nidsToSelect.length === 0 && !this.commandPressed) {
        this.deselectAll(true);
      } else {
        this.selectBlocks(nidsToSelect);
      }
    }

    this.setState({
      firstMousePos: undefined,
      dragging: false,
    });
    this.recalcSize();
  }

  onMouseMove(e) {
    e.stopPropagation();

    const {svgComponent: {refs: {svg}}} = this.refs;

    // Get svg element position to substract offset top and left
    const svgRect = svg.getBoundingClientRect();

    this.setState({
      mousePos: {
        x: e.pageX - svgRect.left,
        y: e.pageY - svgRect.top
      }
    });
  }

  handleBlockStart(nid, pos) {
    this.preventDrawingBox = true;
    if (this.props.onBlockStartMove) {
      this.props.onBlockStartMove(nid, pos);
    }
    this.initialPos = pos;
    if (this.selectedNIDs.indexOf(nid) < 0) {
      this.moveOnlyCurrentBlock = true;
    } else {
      this.moveOnlyCurrentBlock = false;
    }
  }

  handleBlockStop(nid) {
    this.preventDrawingBox = false;
    const d = this.state.data;
    const selectedNIDs = new Set(this.selectedNIDs);
    for (let ii = 0; ii < d.nodes.length; ++ii) {
      if (selectedNIDs.has(d.nodes[ii]._id) || (this.moveOnlyCurrentBlock && d.nodes[ii]._id === nid)) {
        const blockPos = {
          x: d.nodes[ii].x,
          y: d.nodes[ii].y,
        };
        this.props.onBlockMove(d.nodes[ii]._id, blockPos);
      }
    }
  }

  handleBlockMove(index, nid, pos) {
    const d = this.state.data;

    // For some reason, we need to treat dragged object differently from selected
    d.nodes[index].x = pos.x;
    d.nodes[index].y = pos.y;

    if (!this.moveOnlyCurrentBlock) {
      const dx = pos.x - this.initialPos.x;
      const dy = pos.y - this.initialPos.y;
      const ts = new ObjectID().toString();
      let idx;
      for (let ii = 0; ii < d.nodes.length; ++ii) {
        if (ii === index) {
          continue;
        }
        idx = this.selectedNIDs.indexOf(d.nodes[ii]._id);
        if (idx < 0) {
          continue;
        }
        d.nodes[ii].x += dx;
        d.nodes[ii].y += dy;
        d.nodes[ii]._ts = ts;   // TODO remove ts?
      }
    }
    this.initialPos = pos;

    this.setState({data: d});
  }

  handleStartConnector(nid, outputIndex) {
    if (!this.state.editable) {
      return;
    }
    this.setState({dragging: true, source: [nid, outputIndex] });
  }

  handleCompleteConnector(nid, inputIndex) {
    if (this.state.dragging) {
      const nodes = this.state.data.nodes;
      const fromBlock = this.getBlockbyId(nodes, this.state.source[0]);
      const fromPinName = fromBlock.outputs[this.state.source[1]].name;
      const toBlock = this.getBlockbyId(nodes, nid);
      const toPinName = toBlock.inputs[inputIndex].name;

      this.props.onNewConnector(fromBlock._id, fromPinName, toBlock._id, toPinName);
    }
    this.setState({dragging: false});
  }

  handleRemoveConnector(connector) {
    this.props.onRemoveConnector(connector);
  }

  handleOutputClick(nid, outputIndex, displayRaw) {
    const nodes = this.state.data.nodes;
    const block = this.getBlockbyId(nodes, nid);
    if (block.node_running_status !== NODE_RUNNING_STATUS.STATIC && this.state.editable) {
      return;
    }
    this.props.onOutputClick(nid, outputIndex, displayRaw);
  }

  handleSpecialParameterClick(nid, specialParameterIndex) {
    this.props.onSpecialParameterClick(nid, specialParameterIndex);
  }

  handleRemoveBlock(nid) {
    if (!this.state.editable) {
      return;
    }
    let i;
    const connectors = this.state.data.connections;
    const connectorsToRemove = [];

    for (i = 0; i < connectors.length; ++i) {
      const connector = connectors[i];
      if (connector.from_block === nid || connector.to_block === nid) {
        connectorsToRemove.push(connector);
      }
    }

    for (i = 0; i < connectorsToRemove.length; ++i) {
      const rmConnector = connectorsToRemove[i];
      this.handleRemoveConnector(rmConnector);
    }

    this.props.onRemoveBlock(nid);
  }

  handleBlockSelect(nid) {
    const selectedNIDsIndex = this.selectedNIDs.indexOf(nid);
    if (selectedNIDsIndex < 0 || this.commandPressed) {
      this.selectBlocks([nid]);
    }
  }

  deselectAll(changeState) {
    this.selectedNIDs = [];
    if (changeState) {
      this.setState({
        selectedNIDs: this.selectedNIDs
      });
    }
    if (this.props.onAllBlocksDeselect) {
      this.props.onAllBlocksDeselect();
    }
  }

  selectBlocks(nids) {
    if (this.commandPressed) {
      for (let ii = 0; ii < nids.length; ++ii) {
        const selectedNIDsIndex = this.selectedNIDs.indexOf(nids[ii]);
        if (selectedNIDsIndex >= 0) {
          this.selectedNIDs.splice(selectedNIDsIndex, 1);
        } else {
          this.selectedNIDs.push(nids[ii]);
        }
      }
    } else {  // !this.commandPressed
      this.selectedNIDs = nids;
    }


    this.setState({
      selectedNIDs: this.selectedNIDs
    });
    this.props.onBlocksSelect(this.selectedNIDs);
  }

  computePinIndexfromLabel(pins, pinLabel) {
    let reval = 0;

    // eslint-disable-next-line no-unused-vars
    for (const pin of pins) {
      if (pin.name === pinLabel) {
        return reval;
      } else {
        reval++;
      }
    }
    throw new Error('Input ' + pinLabel + ' not found');
  }

  // TODO wth?
  getBlockbyId(nodes, nid) {
    let reval = 0;

    // eslint-disable-next-line no-unused-vars
    for (const block of nodes) {
      if (block._id === nid) {
        return nodes[reval];
      } else {
        reval++;
      }
    }
    throw new Error('Block ' + nid + ' not found');
  }

  render() {
    const nodes = this.state.data.nodes;
    const connectors = this.state.data.connections;
    const { mousePos, dragging, selectedNIDs, graphId, selectedConnector } = this.state;
    const { connectDropTarget } = this.props;

    let i = 0;
    let newConnector = null;

    if (dragging) {
      const block_id = this.state.source[0];
      const out_index = this.state.source[1];
      const sourceBlock = this.getBlockbyId(nodes, block_id);
      const out_name = sourceBlock.outputs[this.state.source[1]].name;
      const connectorStart = computeOutOffsetByIndex(sourceBlock.x, sourceBlock.y, out_index);
      const connectorEnd = {x: this.state.mousePos.x, y: this.state.mousePos.y};

      newConnector = <Spline
                       start={connectorStart}
                       end={connectorEnd}
                       color={intToRGB(hashCode(block_id + out_name))}
                       readonly={!this.state.editable}
                     />;
    }

    let splineIndex = 0;

    const keyHandlers = {
      deletePressed: () => {
        if (this.selectedNIDs.length > 0) {
          for (let ii = 0; ii < this.selectedNIDs.length; ++ii) {
            this.handleRemoveBlock(this.selectedNIDs[ii]);
          }
        } else if (selectedConnector) {
          this.handleRemoveConnector(selectedConnector);
        }
      },
      copyPressed: () => {
        if (this.selectedNIDs.length > 0 && this.props.onCopyBlock) {
          const selectedNIDsSet = new Set(this.selectedNIDs);
          const filteredConnectors = this.state.data.connections.filter(
            connector => {
              return selectedNIDsSet.has(connector.from_block) || selectedNIDsSet.has(connector.to_block);
            }
          );
          const copyList = {
            nids: this.selectedNIDs,
            connectors: filteredConnectors,
          };
          this.props.onCopyBlock(copyList, getScrollOffset());
        }
      },
      pastePressed: () => {
        if (this.state.editable && this.props.onPasteBlock) {
          this.props.onPasteBlock(getScrollOffset());
        }
      },
      commandDown: () => {
        this.commandPressed = true;
      },
      commandUp: () => {
        this.commandPressed = false;
      },
      savePressed: () => {
        if (this.props.onSavePressed) {
          this.props.onSavePressed();
        }
      },
    };

    const selectedNIDsSet = new Set(selectedNIDs);

    return connectDropTarget(
      <div className={'GraphRoot' + (this.state.editable ? ' editable' : ' readonly')}
        onMouseDown={(e) => this.onMouseDown(e)}>
        <HotKeys handlers={keyHandlers} keyMap={KEY_MAP}>
          {nodes.map((block) => {
            const selectedBlock = selectedNIDs.indexOf(block._id) > -1;
            return <Block
                      index={i++}
                      node={block}
                      highlight={block.highlight || false}
                      key={graphId +
                        block._id +
                        (selectedBlock ? '1' : '0') +
                        (block.node_running_status ? block.node_running_status : "static") +
                        block.highlight +
                        block._ts +
                        (block.cache_url ? 'c' : 'r') +
                        block.description
                      }
                      onBlockStart={(nid, pos) => this.handleBlockStart(nid, pos)}
                      onBlockStop={(nid, pos) => this.handleBlockStop(nid, pos)}
                      onBlockMove={(index, nid, pos) => this.handleBlockMove(index, nid, pos)}

                      onStartConnector={(nid, outputIndex) => this.handleStartConnector(nid, outputIndex)}
                      onCompleteConnector={(nid, inputIndex) => this.handleCompleteConnector(nid, inputIndex)}
                      onOutputClick={(nid, outputIndex, displayRaw) => this.handleOutputClick(nid, outputIndex, displayRaw)}
                      onSpecialParameterClick={(nid, outputIndex) => this.handleSpecialParameterClick(nid, outputIndex)}

                      onBlockSelect={(nid) => {
                        this.handleBlockSelect(nid);
                      }}
                      onBlockDeselect={(nid) => {
                        this.handleBlockDeselect(nid);
                      }}
                      onBlockRemove={(nid) => {
                        this.handleRemoveBlock(nid);
                      }}

                      selected={selectedBlock}
                      readonly={!this.state.editable || block.node_running_status === NODE_RUNNING_STATUS.SPECIAL}
                    />;
          })}

          {/* render our connectors */}

          <SVGComponent height={this.height} width={this.width} ref="svgComponent" className="svg-graph">
            {
              connectors.filter(
                connector => {
                  return connectors.length < 50 ||
                    selectedNIDsSet.size === 0 ||
                    selectedNIDsSet.has(connector.from_block) ||
                    selectedNIDsSet.has(connector.to_block);
                }
                ).map(
                  connector => {
                    const fromBlock = this.getBlockbyId(nodes, connector.from_block);
                    const toBlock = this.getBlockbyId(nodes, connector.to_block);

                    const splinestart = computeOutOffsetByIndex(fromBlock.x, fromBlock.y, this.computePinIndexfromLabel(fromBlock.outputs, connector.from));
                    const splineend = computeInOffsetByIndex(toBlock.x, toBlock.y, this.computePinIndexfromLabel(toBlock.inputs, connector.to));

                    return <Spline
                      start={splinestart}
                      end={splineend}
                      key={splineIndex++}
                      mousePos={mousePos}
                      color={intToRGB(hashCode(connector.from_block + connector.from))}
                      onRemove={() => {
                        this.handleRemoveConnector(connector);
                      }}
                      onSelected={() => {
                        this.setState({selectedConnector: connector});
                      }}
                      onDeselected={() => {
                        this.setState({selectedConnector: null});
                      }}
                      readonly={!this.state.editable}
                    />;
                  }
                )
            }

            {/* this is our new connector that only appears on dragging */}
            {newConnector}

            {
              (this.state.firstMousePos && this.state.mousePos && !dragging) &&
              <rect
                className="select-rect"
                width={Math.abs(this.state.firstMousePos.x - this.state.mousePos.x)}
                height={Math.abs(this.state.firstMousePos.y - this.state.mousePos.y)}
                x={Math.min(this.state.firstMousePos.x, this.state.mousePos.x)}
                y={Math.min(this.state.firstMousePos.y, this.state.mousePos.y)}
              />
            }

          </SVGComponent>
        </HotKeys>
      </div>
    );
  }
}

export default DropTarget(ItemTypes.NODE_ITEM, boxTarget, (connect, monitor) => ({
  connectDropTarget: connect.dropTarget(),
  isOver: monitor.isOver(),
  canDrop: monitor.canDrop(),
}))(ReactBlockGraph);
