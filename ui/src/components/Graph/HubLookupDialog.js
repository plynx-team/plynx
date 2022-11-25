import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Dialog from '../Dialogs/Dialog';

import HubPanel from './HubPanel';

export default class HubLookupDialog extends Component {
  static propTypes = {
    kind: PropTypes.string.isRequired,
    hubEntryItem: PropTypes.func.isRequired,
    onClose: PropTypes.func.isRequired,
    hiddenSearch: PropTypes.string,
  };

  constructor(props) {
    super(props);
    this.state = {};
  }

  render() {
    return (
      <Dialog className='HubLookupDialog'
              onClose={() => {
                this.props.onClose();
              }}
              width={280}
              height={400}
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
