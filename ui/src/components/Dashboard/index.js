import React, { Component } from 'react';
import PropTypes from 'prop-types';
import MasterState from './MasterState';

import './style.css';

export default class Dashboard extends Component {
  static propTypes = {
    history: PropTypes.object,
  };

  constructor(props) {
    super(props);
    document.title = 'Dashboard - PLynx';
  }

  render() {
    return (
      <div className="dashboard">
        <div className="dashboard-item">
          <MasterState history={this.props.history} />
        </div>
      </div>
    );
  }
}
