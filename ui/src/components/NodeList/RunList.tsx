import React, { Component } from 'react';
import BaseList from './BaseList';
import { makeControlSeparator } from '../Common/ControlButton';
import { COLLECTIONS } from '../../constants';
import { renderNodeItem, NODE_ITEM_HEADER } from './NodeListItem';
import { addStyleToTourSteps, TourStep } from '../../utils';

const renderItem = renderNodeItem(COLLECTIONS.RUNS, 'node_running_status');

const TOUR_STEPS: TourStep[] = [
  {
    selector: '.list',
    content: 'Plynx will keep history of all of the Runs. You may explore as well as Clone successful ones.',
  },
  {
    selector: '.ListPage .SearchBar',
    content: 'Please use search bar to filter them.',
  },
];

export interface RunListPageProps {
  search?: string;
  showControlls?: boolean;
}

export default class RunListPage extends Component<RunListPageProps> {
  tourSteps: TourStep[];

  MENU_PANEL_DESCRIPTOR = [
    {
      render: makeControlSeparator,
      props: { key: 'separator_1' },
    },
  ];

  constructor(props: RunListPageProps) {
    super(props);
    this.tourSteps = addStyleToTourSteps(TOUR_STEPS);
    document.title = 'Runs - PLynx';
  }

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
        />
      </div>
    );
  }
}
