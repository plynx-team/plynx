import React, { Component } from 'react';
import PropTypes from 'prop-types';
import './LoadingScreen.css';

export default class LoadingScreen extends Component {
  render() {
    return (
      <div className="LoadingScreen" style={this.props.style}>
        <div className="loader">
          Loading...
        </div>
      </div>
    );
  }
}

export class SimpleLoader extends Component {
  render() {
    return (
      <div className="simple-loader" style={this.props.style}>
        <div className="loader">
          Loading...
        </div>
      </div>
    );
  }
}


LoadingScreen.propTypes = {
  style: PropTypes.object,
};

SimpleLoader.propTypes = {
  style: PropTypes.object,
};
