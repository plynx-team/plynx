// src/components/About/index.js
import React, { Component } from 'react';
import { GRAPH_RUNNING_STATUS } from '../../constants.js';
import makeControlButton from '../Common/controlButton.js'
import './OutputItem.css';


export default class Controls extends Component {
  render() {
    return (
      <div className={this.props.className + ' ' + (this.props.readonly ? 'readonly' : 'editable')}>
        {!this.props.readonly &&
          makeControlButton({
            img: 'save.svg',
            text: 'Save',
            func: () => {this.props.onSave()},
          })
        }
        {!this.props.readonly &&
          makeControlButton({
            img: 'check-square.svg',
            text: 'Validate',
            func: () => {this.props.onValidate()},
          })
        }
        {!this.props.readonly &&
          makeControlButton({
            img: 'play.svg',
            text: 'Run',
            func: () => {this.props.onApprove()},
          })
        }
        {!this.props.readonly &&
          makeControlButton({
            img: 'trending-up.svg',
            text: 'Upgrade Nodes',
            func: () => {this.props.onUpgradeNodes()},
          })
        }
        {makeControlButton({
          img: 'rearrange.svg',
          text: 'Rearrange nodes',
          func: () => {this.props.onRearrange()},
        })}
        {makeControlButton({
          img: 'copy.svg',
          text: 'Clone',
          func: () => {this.props.onClone()},
        })}
        {(this.props.graphRunningStatus === GRAPH_RUNNING_STATUS.RUNNING || this.props.graphRunningStatus === GRAPH_RUNNING_STATUS.FAILED_WAITING) &&
          makeControlButton({
            img: 'x.svg',
            text: 'Cancel',
            func: () => {this.props.onCancel()},
          })
        }
      </div>
    );
  }
}
