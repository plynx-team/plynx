// src/components/About/index.js
import React, { Component } from 'react';
import './DemoScreen.css';

export default class DemoScreen extends Component {
  render() {
    return (
      <div className="DemoScreen"
           style={this.props.style}
           onClick={() => this.props.onClose()}>
        <div className="message">
          Please hit the <a href={null}
             onClick={(e) => {e.preventDefault(); this.props.onApprove()}}
             className="control-button">
             <img src="/icons/play.svg" alt=""/> Run
          </a> button to run the demo pipeline
        </div>
      </div>
    );
  }
}
