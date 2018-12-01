// src/components/NotFound/index.js
import React, { Component } from 'react';
import MasterState from './MasterState'

import './style.css';

export default class Dashboard extends Component {
  constructor(props) {
    super(props);
    document.title = "Dashboard - Plynx";
  }

  render() {
    return (
      <div className='dashboard'>
        <div className='dashboard-item'>
          <MasterState />
        </div>
      </div>
    );
  }
}
