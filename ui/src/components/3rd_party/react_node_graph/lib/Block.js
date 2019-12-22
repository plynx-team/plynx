import React from 'react';
import PropTypes from 'prop-types';
import BlockInputList from './BlockInputList';
import BlockOuputList from './BlockOutputList';
import ParameterList from './ParameterList';
import {PluginsConsumer} from '../../../../contexts';
import { NODE_STATUS, NODE_RUNNING_STATUS } from '../../../../constants';

const Draggable = require('react-draggable');


class Block extends React.Component {
  static propTypes = {
    title: PropTypes.string.isRequired,
    description: PropTypes.string.isRequired,
    cacheUrl: PropTypes.string.isRequired,
    highlight: PropTypes.bool.isRequired,
    index: PropTypes.number.isRequired,
    inputs: PropTypes.array.isRequired,
    nid: PropTypes.string.isRequired,
    nodeRunningStatus: PropTypes.oneOf(Object.values(NODE_RUNNING_STATUS)).isRequired,
    nodeStatus: PropTypes.oneOf(Object.values(NODE_STATUS)).isRequired,
    onBlockMove: PropTypes.func.isRequired,
    onBlockRemove: PropTypes.func.isRequired,
    onBlockSelect: PropTypes.func.isRequired,
    onBlockStart: PropTypes.func.isRequired,
    onBlockStop: PropTypes.func.isRequired,
    onCompleteConnector: PropTypes.func.isRequired,
    onOutputClick: PropTypes.func.isRequired,
    onSpecialParameterClick: PropTypes.func.isRequired,
    onStartConnector: PropTypes.func.isRequired,
    outputs: PropTypes.array.isRequired,
    pos: PropTypes.shape({
      x: PropTypes.number.isRequired,
      y: PropTypes.number.isRequired,
    }).isRequired,
    readonly: PropTypes.bool.isRequired,
    selected: PropTypes.bool.isRequired,
    specialParameterNames: PropTypes.array.isRequired,
  }

  constructor(props) {
    super(props);
    this.state = {
      selected: props.selected,
      readonly: props.readonly,
      highlight: props.highlight,
      cacheUrl: props.cacheUrl
    };
  }

  handleDragStart(event, ui) {
    this.props.onBlockStart(this.props.nid, ui);
  }

  handleDragStop() {
    this.props.onBlockStop(this.props.nid);
  }

  handleDrag(event, ui) {
    this.props.onBlockMove(this.props.index, this.props.nid, ui);
  }

  shouldComponentUpdate(nextProps, nextState) {
    return this.state.selected !== nextState.selected;
  }

  onStartConnector(index) {
    this.props.onStartConnector(this.props.nid, index);
  }

  onOutputClick(index) {
    this.props.onOutputClick(this.props.nid, index);
  }

  onSpecialParameterClick(index) {
    this.props.onSpecialParameterClick(this.props.nid, index);
  }

  onCompleteConnector(index) {
    this.props.onCompleteConnector(this.props.nid, index);
  }

  handleClick(e) {
    e.stopPropagation();
    if (this.props.onBlockSelect) {
      this.props.onBlockSelect(this.props.nid);
    }
  }

  handleRemove(e) {
    e.preventDefault();
    e.stopPropagation();
    this.props.onBlockRemove(this.props.nid);
  }

  render() {
    let blockClass = '';
    blockClass =
      'node' + (this.state.selected ? ' selected' : '')
      + ' running-status-' + this.props.nodeRunningStatus.toLowerCase()
      + ' status-' + this.props.nodeStatus.toLowerCase()
      + (this.state.highlight ? ' error-highlight' : '')
      + (this.state.readonly ? ' readonly' : ' editable');

    return (
      <div onClick={(e) => {
        this.handleClick(e);
      }} style={{position: 'relative'}}>
        <Draggable
          defaultPosition={{x: this.props.pos.x, y: this.props.pos.y}}
          handle=".node-header,.node-title,.node-content"
          onStart={(event, ui) => this.handleDragStart(event, ui)}
          onStop={() => this.handleDragStop()}
          onDrag={(event, ui) => this.handleDrag(event, ui)}
          // grid={[15, 15]}
          >
        <section className={blockClass} style={{zIndex: 10000}} >
            <header className="node-header">
              <span className="node-title">{this.props.title}</span>
              {
                !this.state.readonly &&
                <div
                  className={'remove'}
                  onClick={(e) => this.handleRemove(e)}
                >
                  &#215;
                </div>
              }
              {
                this.state.cacheUrl &&
                <a href={this.state.cacheUrl}
                  className={'remove'}
                >
                  <img
                    src={"/icons/cached.svg"}
                    width="10"
                    height="10"
                    alt="cached"
                    />
                </a>
              }
            </header>
            <div className="node-description">&ldquo;{this.props.description}&rdquo;</div>
            <PluginsConsumer>
            {
              plugins_dict => <div className="node-content" onClick={(e) => {
                this.handleClick(e);
              }}>
                <BlockInputList
                              items={this.props.inputs}
                              onCompleteConnector={(index) => this.onCompleteConnector(index)}
                              resources_dict={plugins_dict.resources_dict}
                              />
                <BlockOuputList
                              items={this.props.outputs}
                              onStartConnector={(index) => this.onStartConnector(index)}
                              onClick={(index) => this.onOutputClick(index)}
                              resources_dict={plugins_dict.resources_dict}
                              />

              </div>
            }
            </PluginsConsumer>
            <ParameterList
                          items={this.props.specialParameterNames}
                          onClick={(index) => this.onSpecialParameterClick(index)} />
        </section>
        </Draggable>
      </div>
    );
  }
}

export default Block;
