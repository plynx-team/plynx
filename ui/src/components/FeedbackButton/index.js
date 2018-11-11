// src/components/NotFound/index.js
import React, { Component } from 'react';

import './style.css';

export default class FeedbackButton extends Component {

  handleClick() {
    this.props.onClick();
  }

  render() {
    var self = this;

    return (
      <div className='FeedbackButton'
           onClick={() => self.handleClick()}>
          Feedback
      </div>
    );
  }
}
