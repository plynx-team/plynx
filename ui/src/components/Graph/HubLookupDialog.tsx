import React, { Component } from 'react';
import Dialog from '../Dialogs/Dialog';
import HubPanel from './HubPanel';

export interface HubLookupDialogProps {
  kind: string;
  hubEntryItem: any;
  onClose: () => void;
  hiddenSearch?: string;
  defaultX?: number;
  defaultY?: number;
}

export default class HubLookupDialog extends Component<HubLookupDialogProps> {
  render() {
    return (
      <Dialog
        className="HubLookupDialog"
        onClose={() => {
          this.props.onClose();
        }}
        width={280}
        height={500}
        defaultX={this.props.defaultX}
        defaultY={this.props.defaultY}
        title="Look up"
        enableResizing
      >
        <HubPanel
          kind={this.props.kind}
          hubEntryItem={this.props.hubEntryItem}
          hiddenSearch={this.props.hiddenSearch}
        />
      </Dialog>
    );
  }
}
