import React, { Component } from 'react';
import PropTypes from 'prop-types';
import BaseList from './baseList';
import { makeControlSeparator } from '../Common/controlButton';
import { COLLECTIONS } from '../../constants';
import { renderNodeItem, NODE_ITEM_HEADER } from './common';
import { addStyleToTourSteps } from '../../utils';


const renderItem = renderNodeItem(COLLECTIONS.RUNS, 'node_running_status');

const TOUR_STEPS = [
  {
    selector: '.list',
    content: 'Plynx will keep history of all of the Runs. You may explore as well as Clone successful ones.',
  },
  {
    selector: '.ListPage .SearchBar',
    content: 'Please use search bar to filter them.',
  },
];

export default class RunListPage extends Component {
  static propTypes = {
    search: PropTypes.string,
  }

  constructor(props) {
    super(props);
    this.tourSteps = addStyleToTourSteps(TOUR_STEPS);
    document.title = "Runs - PLynx";
  }

  MENU_PANEL_DESCRIPTOR = [
    {
      render: makeControlSeparator,
      props: {key: 'separator_1'}
    },
  ];

  render() {
    return (
        <div className="node-list-view">
            <BaseList
                menuPanelDescriptor={this.MENU_PANEL_DESCRIPTOR}
                tag="node-list-item"
                header={NODE_ITEM_HEADER}
                search={this.props.search}
                renderItem={renderItem}
                collection={COLLECTIONS.RUNS}
            >
            </BaseList>
        </div>
    );
  }
}
