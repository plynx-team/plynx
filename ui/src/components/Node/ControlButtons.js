// src/components/About/index.js
import React, { Component } from 'react';
import { NODE_STATUS } from '../../constants.js';

export default class ControlButtons extends Component {
  constructor(props) {
    super(props);
    this.state = {
      readOnly: props.readOnly
    };
  }

  handleSave() {
    this.props.onSave();
  }

  handleSaveApprove() {
    this.props.onSaveApprove();
  }

  handleClone() {
    this.props.onClone();
  }

  handleDeprecate() {
    this.props.onDeprecate();
  }

  render() {
    return (
      <div className="ControlButtons">
        {!this.state.readOnly &&
          <a href={null}
             onClick={(e) => {e.preventDefault(); this.props.onSave()}}
             className="control-button">
             <img src="/icons/save.svg" alt="save"/> Save
          </a>
        }
        {!this.state.readOnly &&
          <a href={null}
             onClick={(e) => {e.preventDefault(); this.props.onSaveApprove()}}
             className="control-button demo">
             <img src="/icons/play.svg" alt="demo"/> Approve
          </a>
        }
        {(!this.props.hideDeprecate && this.props.nodeStatus === NODE_STATUS.READY) &&
            <a href={null}
               onClick={(e) => {e.preventDefault(); this.props.onDeprecate()}}
               className="control-button">
               <img src="/icons/x.svg" alt="deprecate"/> Deprecate
            </a>
        }
        <a href={null}
           onClick={(e) => {e.preventDefault(); this.props.onPreview()}}
           className="control-button">
           <img src="/icons/preview.svg" alt="preview"/> Preview
        </a>
        <a href={null}
           onClick={(e) => {e.preventDefault(); this.props.onClone()}}
           className="control-button">
           <img src="/icons/copy.svg" alt="clone"/> Clone
        </a>
      </div>
    );
  }
}
