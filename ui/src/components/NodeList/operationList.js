import React, { Component } from 'react';
import BaseList from './baseList';
import FileUploadDialog from '../Dialogs/FileUploadDialog';
import { makeControlSeparator } from '../Common/controlButton';
import { COLLECTIONS, VIRTUAL_COLLECTIONS } from '../../constants';
import { renderNodeItem, NODE_ITEM_HEADER } from './common';
import {PluginsConsumer} from '../../contexts';

const renderItem = renderNodeItem(COLLECTIONS.TEMPLATES, 'node_status');

export default class OperationListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Operations - PLynx";
    this.state = {
      uploadOperation: null,
    };
  }

  MENU_PANEL_DESCRIPTOR = [
    {
      render: makeControlSeparator,
      props: {key: 'separator_1'}
    },
  ];

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
                    extraSearch={{virtual_collection: VIRTUAL_COLLECTIONS.OPERATIONS}}
                    header={NODE_ITEM_HEADER}
                    renderItem={renderItem}
                    virtualCollection={VIRTUAL_COLLECTIONS.OPERATIONS}
                    collection={COLLECTIONS.TEMPLATES}
                    onUploadDialog={
                        (operation_descriptor) => {
                          console.log(operation_descriptor);
                          this.setState({
                            uploadOperation: operation_descriptor
                          });
                        }
                    }
                >
                {this.state.uploadOperation &&
                    <PluginsConsumer>
                    { plugins_info => <FileUploadDialog
                            onClose={() => this.handleCloseDialog()}
                            uploadOperation={this.state.uploadOperation}
                            plugins_info={plugins_info}
                          />
                     }
                     </PluginsConsumer>
                }
                </BaseList>
            </div>
    );
  }
}
