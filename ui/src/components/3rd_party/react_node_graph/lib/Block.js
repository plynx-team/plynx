import React from 'react';
import PropTypes from 'prop-types';
import BlockInputList from './BlockInputList';
import BlockOuputList from './BlockOutputList';
import ParameterList from './ParameterList';
import {PluginsConsumer} from '../../../../contexts';
import cookie from 'react-cookies';
import { NODE_STATUS, NODE_RUNNING_STATUS, OPERATION_VIEW_SETTING } from '../../../../constants';

import Icon from '../../../Common/Icon';

const Draggable = require('react-draggable');


class Block extends React.Component {
  static propTypes = {
    node: PropTypes.shape({
      _id: PropTypes.string.isRequired,
      title: PropTypes.string.isRequired,
      description: PropTypes.string.isRequired,
      kind: PropTypes.string.isRequired,
      cache_url: PropTypes.string,
      node_running_status: PropTypes.oneOf(Object.values(NODE_RUNNING_STATUS)).isRequired,
      inputs: PropTypes.array.isRequired,
      outputs: PropTypes.array.isRequired,
      node_status: PropTypes.oneOf(Object.values(NODE_STATUS)).isRequired,
      x: PropTypes.number.isRequired,
      y: PropTypes.number.isRequired,
    }),

    highlight: PropTypes.bool.isRequired,
    index: PropTypes.number.isRequired,
    readonly: PropTypes.bool.isRequired,
    selected: PropTypes.bool.isRequired,

    onBlockMove: PropTypes.func.isRequired,
    onBlockRemove: PropTypes.func.isRequired,
    onBlockSelect: PropTypes.func.isRequired,
    onBlockStart: PropTypes.func.isRequired,
    onBlockStop: PropTypes.func.isRequired,
    onCompleteConnector: PropTypes.func.isRequired,
    onOutputClick: PropTypes.func.isRequired,
    onSpecialParameterClick: PropTypes.func.isRequired,
    onStartConnector: PropTypes.func.isRequired,
  }

  constructor(props) {
    super(props);

    const settings = cookie.load('settings');
    if (settings) {
      this.kindAndTitle = settings.node_view_mode === OPERATION_VIEW_SETTING.KIND_AND_TITLE;
    } else {
      console.error('Could not find settings');
    }

    this.state = {
      selected: props.selected,
      readonly: props.readonly,
      highlight: props.highlight,
      cache_url: props.cache_url, // eslint-disable-line
    };
  }

  handleDragStart(event, ui) {
    this.props.onBlockStart(this.props.node._id, ui);
  }

  handleDragStop() {
    this.props.onBlockStop(this.props.node._id);
  }

  handleDrag(event, ui) {
    this.props.onBlockMove(this.props.index, this.props.node._id, ui);
  }

  shouldComponentUpdate(nextProps, nextState) {
    return this.state.selected !== nextState.selected;
  }

  onStartConnector(index) {
    this.props.onStartConnector(this.props.node._id, index);
  }

  onOutputClick(index) {
    this.props.onOutputClick(this.props.node._id, index);
  }

  onSpecialParameterClick(index) {
    this.props.onSpecialParameterClick(this.props.node._id, index);
  }

  onCompleteConnector(index) {
    this.props.onCompleteConnector(this.props.node._id, index);
  }

  handleClick(e) {
    e.stopPropagation();
    if (this.props.onBlockSelect) {
      this.props.onBlockSelect(this.props.node._id);
    }
  }

  handleRemove(e) {
    e.preventDefault();
    e.stopPropagation();
    this.props.onBlockRemove(this.props.node._id);
  }

  render() {
    const blockClass = [
      'node',
      this.state.selected ? 'selected' : '',
      `running-status-${this.props.node.node_running_status.toLowerCase()}`,
      `status-${this.props.node.node_status.toLowerCase()}`,
        (this.state.highlight ? 'error-highlight' : ''),
        (this.state.readonly ? 'readonly' : 'editable'),
      `node-${this.props.node._id}`,
    ].join(' ');

    return (
      <PluginsConsumer>
      {
        plugins_dict => <div onClick={(e) => {
          this.handleClick(e);
        }} style={{position: 'relative'}}>
          <Draggable
            defaultPosition={{x: this.props.node.x, y: this.props.node.y}}
            handle=".node-header,.node-header-title,.node-content"
            onStart={(event, ui) => this.handleDragStart(event, ui)}
            onStop={() => this.handleDragStop()}
            onDrag={(event, ui) => this.handleDrag(event, ui)}
            // grid={[15, 15]}
            >
            <section className={blockClass} style={{zIndex: 10000}} >
                <header className="node-header">
                  <span className="node-header-title">
                      <Icon
                        type_descriptor={plugins_dict.executors_info[this.props.node.kind]}
                        className="operation-icon"
                      />
                      <div className="operation-title-text">
                        {this.kindAndTitle ? plugins_dict.executors_info[this.props.node.kind].title : this.props.node.title}
                      </div>
                  </span>
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
                    this.props.node.cache_url &&
                    <a href={this.props.node.cache_url}
                      className={'remove'}
                    >
                      <img
                        src={"/icons/cached.svg"}
                        width="11"
                        height="11"
                        alt="cached"
                        />
                    </a>
                  }
                </header>
                <div className="node-title">
                    {this.kindAndTitle ? this.props.node.title : this.props.node.description}
                </div>
                <div className="node-content" onClick={(e) => {
                  this.handleClick(e);
                }}>
                    <BlockInputList
                                  items={this.props.node.inputs}
                                  onCompleteConnector={(index) => this.onCompleteConnector(index)}
                                  resources_dict={plugins_dict.resources_dict}
                                  />
                    <BlockOuputList
                                  items={this.props.node.outputs}
                                  onStartConnector={(index) => this.onStartConnector(index)}
                                  onClick={(index) => this.onOutputClick(index)}
                                  resources_dict={plugins_dict.resources_dict}
                                  />

                </div>
                <ParameterList
                    items={[]}
                    onClick={(index) => this.onSpecialParameterClick(index)}
                />
            </section>
          </Draggable>
      </div>
      }
      </PluginsConsumer>
    );
  }
}

export default Block;
