// src/components/About/index.js
import React, { Component } from 'react';
import Dialog from './Dialog.js'
import cookie from 'react-cookies'


export default class APIDialog extends Component {
  constructor(props) {
    super(props);
    this.state = {
      token: cookie.load('refresh_token'),
    }
  }

  render() {
    return (
      <Dialog className='api-dialog'
              onClose={() => {this.props.onClose()}}
              width={900}
              height={300}
              title={'python API'}
              enableResizing={false}
      >
        <div className="api-dialog-content selectable">
          <pre>
            Hello, {this.state.token}
          </pre>
        </div>

      </Dialog>
    );
  }
}
