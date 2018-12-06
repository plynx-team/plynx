import React from 'react';
import BlockInputList from './BlockInputList';
import BlockOuputList from './BlockOutputList';
import ParameterList from './ParameterList';

var Draggable = require('react-draggable');

class Block extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      selected: props.selected,
      readonly: props.readonly,
      highlight: props.highlight,
      cacheUrl: props.cacheUrl
    }
  }

  handleDragStart(event, ui) {
    this.props.onBlockStart(this.props.nid, ui);
  }

  handleDragStop(event, ui) {
    this.props.onBlockStop(this.props.nid, ui.position);
  }

  handleDrag(event, ui) {
    this.props.onBlockMove(this.props.index, ui.position);
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
    let blockClass = ''
    blockClass =
      'node' + (this.state.selected ? ' selected' : '')
      + ' running-status-' + this.props.nodeRunningStatus.toLowerCase()
      + ' status-' + this.props.nodeStatus.toLowerCase()
      + (this.state.highlight ? ' error-highlight' : '')
      + (this.state.readonly ? ' readonly' : ' editable');

    return (
      <div onClick={(e) => {this.handleClick(e)}}>
        <Draggable
          start={{x:this.props.pos.x,y:this.props.pos.y}}
          handle=".node-header,.node-title,.node-content"
          onStart={(event, ui)=>this.handleDragStart(event, ui)}
          onStop={(event, ui)=>this.handleDragStop(event, ui)}
          onDrag={(event, ui)=>this.handleDrag(event, ui)}
          //grid={[15, 15]}
          >
        <section className={blockClass} style={{zIndex:10000}} onClick={(e) => {this.handleClick(e)}}>
            <header className="node-header" style={{backgroundColor:this.props.color}} onClick={(e) => {this.handleClick(e)}}>
              <span className="node-title">{this.props.title}</span>
              {
                !this.state.readonly &&
                <a href={null}
                  className={'remove'}
                  onClick={(e) => this.handleRemove(e)}
                >
                  &#215;
                </a>
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
            <div className="node-content" onClick={(e) => {this.handleClick(e)}}>
              <BlockInputList
                            items={this.props.inputs}
                            onCompleteConnector={(index)=>this.onCompleteConnector(index)} />
              <BlockOuputList
                            items={this.props.outputs}
                            onStartConnector={(index)=>this.onStartConnector(index)}
                            onClick={(index)=>this.onOutputClick(index)} />

            </div>
            <ParameterList
                          items={this.props.specialParameterNames}
                          onClick={(index)=>this.onSpecialParameterClick(index)} />
        </section>
        </Draggable>
      </div>
    );
  }
}

export default Block;
