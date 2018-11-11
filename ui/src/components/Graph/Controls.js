// src/components/About/index.js
import React, { Component } from 'react';
import { GRAPH_RUNNING_STATUS } from '../../constants.js';
import './OutputItem.css';

export default class Controls extends Component {
  render() {
    //{{pathname: '/graphs/' + this.state.graphId, query: {node: this.state.nodeId, output_preview: this.state.resourceName}}}
    return (
      <div className={this.props.className + ' ' + (this.props.readonly ? 'readonly' : 'editable')}>
        {!this.props.readonly &&
          <a href={null}
             onClick={(e) => {e.preventDefault(); this.props.onSave()}}
             className="control-button">
             <img src="/icons/save.svg" alt="save" /> Save
          </a>
        }
        {!this.props.readonly &&
          <a href={null}
             onClick={(e) => {e.preventDefault(); this.props.onValidate()}}
             className="control-button">
             <img src="/icons/check-square.svg" alt="validate" /> Validate
          </a>
        }
        {!this.props.readonly &&
          <a href={null}
             onClick={(e) => {e.preventDefault(); this.props.onApprove()}}
             className="control-button demo"
             >
             <img src="/icons/play.svg" alt="run" /> Run
          </a>
        }
        {!this.props.readonly &&
          <a href={null}
             onClick={(e) => {e.preventDefault(); this.props.onUpgradeNodes()}}
             className="control-button"
             >
             <img src="/icons/trending-up.svg" alt="upgrade" /> Upgrade Nodes
          </a>
        }
        <a href={null}
           onClick={(e) => {e.preventDefault(); this.props.onRearrange()}}
           className={"control-button"}>
           <img src="/icons/rearrange.svg" alt="rearrange" /> Rearrange nodes
        </a>
        <a href={null}
           onClick={(e) => {e.preventDefault(); this.props.onClone()}}
           className={"control-button" + (this.props.readonly ? " demo" : "") }>
           <img src="/icons/copy.svg" alt="clone" /> Clone
        </a>
        {this.props.graphRunningStatus === GRAPH_RUNNING_STATUS.RUNNING &&
          <a href={null}
             onClick={(e) => {e.preventDefault(); this.props.onCancel()}}
             className="control-button">
             <img src="/icons/x.svg" alt="deprecate"/> Cancel
          </a>
        }
      </div>
    );
  }
}
