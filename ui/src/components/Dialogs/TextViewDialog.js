// src/components/About/index.js
import React, { Component } from 'react';
import Dialog from './Dialog.js'


export default class TextViewDialog extends Component {
  constructor(props) {
    super(props);
    this.state = {
      text: props.text,
      title: props.title
    };
  }

  render() {
    return (
      <Dialog className='TextViewDialog'
              onClose={() => {this.props.onClose()}}
              width={900}
              height={300}
              title={this.state.title}
              enableResizing={true}
      >
        <div className="PreviewBoxContent selectable">
          <pre>
            {this.state.text}
          </pre>
        </div>

      </Dialog>
    );
  }
}
