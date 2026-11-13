import React, { Component } from 'react';
import BaseList from './BaseList';
import FileUploadDialog from '../Dialogs/FileUploadDialog';
import { makeControlSeparator } from '../Common/ControlButton';
import { COLLECTIONS, VIRTUAL_COLLECTIONS } from '../../constants';
import { renderNodeItem, NODE_ITEM_HEADER } from './NodeListItem';
import { PluginsConsumer } from '../../contexts';
import { PluginsDict } from '../../types';

const renderItem = renderNodeItem(COLLECTIONS.TEMPLATES, 'node_status');

interface OperationListPageState {
  uploadOperation: any;
}

export default class OperationListPage extends Component<any, OperationListPageState> {
  MENU_PANEL_DESCRIPTOR = [
    {
      render: makeControlSeparator,
      props: { key: 'separator_1' },
    },
  ];

  constructor(props: any) {
    super(props);
    document.title = 'Operations - PLynx';
    this.state = {
      uploadOperation: null,
    };
  }

  handleCloseDialog() {
    this.setState({
      uploadOperation: null,
    });
  }

  render() {
    return (
      <div className="node-list-view">
        <BaseList
          menuPanelDescriptor={this.MENU_PANEL_DESCRIPTOR}
          tag="node-list-item"
          extraSearch={{ virtual_collection: VIRTUAL_COLLECTIONS.OPERATIONS }}
          header={NODE_ITEM_HEADER}
          renderItem={renderItem}
          virtualCollection={VIRTUAL_COLLECTIONS.OPERATIONS}
          collection={COLLECTIONS.TEMPLATES}
          onUploadDialog={(operationDescriptor: any) => {
            this.setState({
              uploadOperation: operationDescriptor,
            });
          }}
        />
        {this.state.uploadOperation && (
          <PluginsConsumer>
            {(plugins_dict: PluginsDict) => (
              <FileUploadDialog
                onClose={() => this.handleCloseDialog()}
                uploadOperation={this.state.uploadOperation}
                plugins_info={plugins_dict}
                onUpload={(node) => {
                  window.location.href = `/${COLLECTIONS.TEMPLATES}/${node._id}`;
                }}
              />
            )}
          </PluginsConsumer>
        )}
      </div>
    );
  }
}
