import React, { Component } from 'react';
import PropTypes from 'prop-types';

export default class SVGComponent extends Component {
  static propTypes = {
    children: PropTypes.array.isRequired,
  }

  render() {
    return <svg style={{zIndex: 9000}} {...this.props} ref="svg">{this.props.children}</svg>;
  }
}
