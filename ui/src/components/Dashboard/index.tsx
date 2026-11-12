import React, { Component } from 'react';
import MasterState from './MasterState';

import './style.css';

export interface DashboardProps {
  history?: any;
}

export default class Dashboard extends Component<DashboardProps> {
  constructor(props: DashboardProps) {
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
