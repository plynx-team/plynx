import React from 'react';
import {HotKeys} from 'react-hotkeys';
import Block from './lib/Block';
import Spline from './lib/Spline';
import SVGComponent from './lib/SVGComponent';

import PropTypes from 'prop-types'
import { DropTarget } from 'react-dnd'
import ItemTypes from '../../../DragAndDropsItemTypes'

import {computeOutOffsetByIndex, computeInOffsetByIndex} from './lib/util';
import { KEY_MAP, NODE_RUNNING_STATUS } from '../../../constants.js';

const boxTarget = {
  drop(props, monitor, component) {
    var graphProps = props;
    var blockObj = monitor.getItem();
    var mousePos = monitor.getClientOffset();

    if (graphProps.onDrop) {
      graphProps.onDrop({nodeContent: blockObj.nodeContent, mousePos: mousePos});
    }
    return { name: 'ReactBlockGraph' }
  },
}

function hashCode(str) { // java String#hashCode
  var hash = 0;
  for (var i = 0; i < str.length; i++) {
     hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return hash;
}

function intToRGB(i){
  var c = (i & 0x00FFFFFF)
      .toString(16)
      .toUpperCase();

  return "00000".substring(0, 6 - c.length) + c;
}

class ReactBlockGraph extends React.Component {

  constructor(props) {
    super(props);

    this.selectedNIDs = [];

    this.state = {
      data : this.props.data,
      source : [],
      dragging: false,
      editable: this.props.editable,
      selectedNIDs: this.selectedNIDs,
      graphId: this.props.graphId
    }

    this.onMouseMove = this.onMouseMove.bind(this);
    this.onMouseUp = this.onMouseUp.bind(this);
    this.commandPressed = false;
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
    this.setState({data: nextProps.data});
  }

  onMouseUp(e) {
    this.setState({dragging:false, });
  }

  onMouseMove(e) {
    e.stopPropagation();

      const {svgComponent: {refs: {svg}}} = this.refs;

      //Get svg element position to substract offset top and left
      const svgRect = svg.getBoundingClientRect();

    this.setState({
        mousePos: {
          x: e.pageX - svgRect.left,
          y: e.pageY - svgRect.top
        }
      });
  }

  handleBlockStart(nid) {
    this.props.onBlockStartMove(nid);
  }

  handleBlockStop(nid, pos) {
    this.props.onBlockMove(nid, pos);
  }

  handleBlockMove(index, pos) {
    let d = this.state.data;

    d.blocks[index].x = pos.left;
    d.blocks[index].y = pos.top;

    this.setState({data : d});
  }

  handleStartConnector(nid, outputIndex) {
    if (!this.state.editable) {
      return;
    }
    this.setState({dragging:true, source:[nid,outputIndex] });
  }

  handleCompleteConnector(nid, inputIndex) {
    if (this.state.dragging) {

      let blocks = this.state.data.blocks;
      let fromBlock = this.getBlockbyId(blocks, this.state.source[0]);
      let fromPinName = fromBlock.fields.out[this.state.source[1]].name;
      let toBlock = this.getBlockbyId(blocks, nid);
      let toPinName = toBlock.fields.in[inputIndex].name;

      this.props.onNewConnector(fromBlock.nid, fromPinName, toBlock.nid, toPinName);
    }
    this.setState({dragging:false});
  }

  handleRemoveConnector(connector) {
    if (this.props.onRemoveConnector) {
      this.props.onRemoveConnector(connector);
    }
  }

  handleOutputClick(nid, outputIndex) {
    let blocks = this.state.data.blocks;
    let block = this.getBlockbyId(blocks, nid);
    if (block.nodeRunningStatus !== NODE_RUNNING_STATUS.STATIC && this.state.editable) {
      return;
    }
    this.props.onOutputClick(nid, outputIndex)
  }

  handleSpecialParameterClick(nid, specialParameterIndex) {
    this.props.onSpecialParameterClick(nid, specialParameterIndex);
  }

  handleRemoveBlock(nid) {
    if (!this.state.editable) {
      return;
    }
    let connectors = this.state.data.connections;
    var connectorsToRemove = [];
    for (var i in connectors) {
      var connector = connectors[i];
      if (connector.from_block === nid || connector.to_block === nid) {
        connectorsToRemove.push(connector);
      }
    }

    for (var j in connectorsToRemove) {
      var rmConnector = connectorsToRemove[j];
      this.handleRemoveConnector(rmConnector);
    }

    this.props.onRemoveBlock(nid);
    console.log(connectors);
  }

  handleBlockSelect(nid) {
    var selectedNIDsIndex = this.selectedNIDs.indexOf(nid);
    if (this.commandPressed) {
      if (selectedNIDsIndex >= 0) {
        this.props.onBlockDeselect(this.selectedNIDs[selectedNIDsIndex]);
        this.selectedNIDs.splice(selectedNIDsIndex, 1);
      } else {
        this.selectedNIDs.push(nid);
      }
    } else {  // !this.commandPressed
      if (selectedNIDsIndex >= 0) {
        return;
      }
      for (var ii = 0; ii < this.selectedNIDs.length; ++ii) {
          this.props.onBlockDeselect(this.selectedNIDs[ii]);
      }
      this.selectedNIDs = [nid];
    }

    this.setState({
      selectedNIDs: this.selectedNIDs
    });
    this.props.onBlocksSelect(this.selectedNIDs);
  }

  deselectAll(changeState) {
    if (this.selectedNIDs.length > 0 && this.props.onBlockDeselect) {
      for (var ii = 0; ii < this.selectedNIDs.length; ++ii) {
          this.props.onBlockDeselect(this.selectedNIDs[ii]);
      }
    }
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
    this.commandPressed = true;
    nids.map(nid => this.handleBlockSelect(nid));
    this.commandPressed = false;
  }

  handleBackgroundClick() {
    console.log("handleBackgroundClick", this.commandPressed);
    if (this.commandPressed) {
      return;
    }
    this.deselectAll(true);
  }

  computePinIndexfromLabel(pins, pinLabel) {
    let reval = 0;

    for (let pin of pins) {
      if (pin.name === pinLabel) {
        return reval;
      } else {
        reval++;
      }

    }
  }

  // TODO wth?
  getBlockbyId(blocks, nid) {
    let reval = 0;

    for (let block of blocks) {
      if (block.nid === nid) {
        return blocks[reval];
      } else {
        reval++;
      }
    }
  }

  render() {
    let blocks = this.state.data.blocks;
    let connectors = this.state.data.connections;
    let { mousePos, dragging, selectedNIDs, graphId, selectedConnector } = this.state;
    const { connectDropTarget } = this.props;

    let i = 0;
    let newConnector = null;

    if (dragging) {

      let block_id = this.state.source[0];
      let out_index = this.state.source[1];
      let sourceBlock = this.getBlockbyId(blocks, block_id);
      let out_name = sourceBlock.fields.out[this.state.source[1]].name;
      let connectorStart = computeOutOffsetByIndex(sourceBlock.x, sourceBlock.y, out_index);
      let connectorEnd = {x:this.state.mousePos.x, y:this.state.mousePos.y};

      newConnector = <Spline
                       start={connectorStart}
                       end={connectorEnd}
                       color={intToRGB(hashCode(block_id + out_name))}
                       readonly={!this.state.editable}
                     />
    }

    let splineIndex = 0;

    var keyHandlers = {
      deletePressed: () => {
        if (this.selectedNIDs.length > 0) {
          for (var ii = 0; ii < this.selectedNIDs.length; ++ii) {
              this.handleRemoveBlock(this.selectedNIDs[ii]);
          }
        } else if (selectedConnector) {
          this.handleRemoveConnector(selectedConnector);
        }
      },
      copyPressed: () => {
        if (this.selectedNIDs.length > 0 && this.props.onCopyBlock) {
          const selectedNIDs = new Set(this.selectedNIDs);
          const connectors = this.state.data.connections.filter(
            connector => {
              return selectedNIDs.has(connector.from_block) || selectedNIDs.has(connector.to_block)
            }
          );
          var copyList = {
            nids: this.selectedNIDs,
            connectors: connectors,
          };
          this.props.onCopyBlock(copyList);
        }
      },
      pastePressed: () => {
        if (this.state.editable && this.props.onPasteBlock) {
          this.props.onPasteBlock();
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
      <div className={'GraphRoot' + (this.state.editable ? ' editable' : ' readonly')} >
        <HotKeys handlers={keyHandlers} keyMap={KEY_MAP}>
          {blocks.map((block) => {
            var selectedBlock = selectedNIDs.indexOf(block.nid) > -1;
            return <Block
                      index={i++}
                      nid={block.nid}
                      color="#000000"
                      title={block.title}
                      description={block.description}
                      inputs={block.fields.in}
                      outputs={block.fields.out}
                      pos={{x : block.x, y: block.y}}
                      highlight={block.highlight}
                      cacheUrl={block.cacheUrl}
                      key={graphId +
                        block.nid +
                        (selectedBlock ? '1' : '0') +
                        (block.nodeRunningStatus ? block.nodeRunningStatus: "static") +
                        block.highlight +
                        block._ts +
                        (block.cacheUrl ? 'c' : 'r') +
                        block.description
                      }
                      nodeRunningStatus={block.nodeRunningStatus ? block.nodeRunningStatus : 'static'}
                      nodeStatus={block.nodeStatus}

                      specialParameterNames={block.specialParameterNames}

                      onBlockStart={(nid)=>this.handleBlockStart(nid)}
                      onBlockStop={(nid, pos)=>this.handleBlockStop(nid, pos)}
                      onBlockMove={(index,pos)=>this.handleBlockMove(index,pos)}

                      onStartConnector={(nid, outputIndex)=>this.handleStartConnector(nid, outputIndex)}
                      onCompleteConnector={(nid, inputIndex)=>this.handleCompleteConnector(nid, inputIndex)}
                      onOutputClick={(nid, outputIndex)=>this.handleOutputClick(nid, outputIndex)}
                      onSpecialParameterClick={(nid, outputIndex)=>this.handleSpecialParameterClick(nid, outputIndex)}

                      onBlockSelect={(nid) => {this.handleBlockSelect(nid)}}
                      onBlockDeselect={(nid) => {this.handleBlockDeselect(nid)}}
                      onBlockRemove={(nid) => {this.handleRemoveBlock(nid)}}

                      selected={selectedBlock}
                      readonly={!this.state.editable}
                    />
          })}

          {/* render our connectors */}

          <SVGComponent height="100%" width="100%" ref="svgComponent"
            onClick={() => {this.handleBackgroundClick()}}>

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
                    let fromBlock = this.getBlockbyId(blocks,connector.from_block);
                    let toBlock = this.getBlockbyId(blocks,connector.to_block);

                    let splinestart = computeOutOffsetByIndex(fromBlock.x, fromBlock.y, this.computePinIndexfromLabel(fromBlock.fields.out, connector.from));
                    let splineend = computeInOffsetByIndex(toBlock.x, toBlock.y, this.computePinIndexfromLabel(toBlock.fields.in, connector.to));

                    return <Spline
                      start={splinestart}
                      end={splineend}
                      key={splineIndex++}
                      mousePos={mousePos}
                      color={intToRGB(hashCode(connector.from_block + connector.from))}
                      onRemove={() => {this.handleRemoveConnector(connector)}}
                      onSelected={() => {this.setState({selectedConnector: connector});}}
                      onDeselected={() => {this.setState({selectedConnector: null});}}
                      readonly={!this.state.editable}
                    />
                  }
                )
            }

            {/* this is our new connector that only appears on dragging */}
            {newConnector}

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
}))(ReactBlockGraph)
