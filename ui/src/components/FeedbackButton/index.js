// src/components/NotFound/index.js
import React, { Component } from 'react';

import './style.css';

export default class FeedbackButton extends Component {
  render() {
    return <a href="mailto:ivan@plynx.com" className='FeedbackButton'>Contact us</a>;
  }
}
