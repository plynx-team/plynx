import React, { Component } from 'react';
import PropTypes from 'prop-types';
import './DemoScreen.css';

export default class DemoScreen extends Component {
  static propTypes = {
    onClose: PropTypes.func.isRequired,
    onApprove: PropTypes.func.isRequired,
    style: PropTypes.object,
  }

  render() {
    return (
      <div className="DemoScreen"
           style={this.props.style}
           onClick={() => this.props.onClose()}>
        <div className="message">
          Please hit the <a href={null}
             onClick={(e) => {
               e.preventDefault();
               this.props.onApprove();
             }}
             className="control-button">
             <img src="/icons/play.svg" alt=""/> Run
          </a> button to run the demo pipeline
        </div>
      </div>
    );
  }
}
