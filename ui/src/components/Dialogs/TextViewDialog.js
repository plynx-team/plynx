import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { makeControlPanel, makeControlButton } from '../Common/controlButton';
import Dialog from './Dialog';


export default class TextViewDialog extends Component {
  static propTypes = {
    text: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    showAlert: PropTypes.func.isRequired,
    onClose: PropTypes.func.isRequired,
  }

  constructor(props) {
    super(props);
    this.state = {
      text: props.text,
      title: props.title
    };
  }

  makeControls() {
    const items = [
      {
        render: makeControlButton,
        props: {
          img: 'copy.svg',
          text: 'Copy',
          func: () => this.handleCopy(),
        },
      },
    ];

    return makeControlPanel(
      {
        props: {
          items: items,
          key: 1
        },
      });
  }

  handleCopy() {
    const copyText = this.state.text;
    const textArea = document.createElement('textarea');
    textArea.textContent = copyText;
    document.body.append(textArea);
    textArea.select();
    document.execCommand("copy");

    this.props.showAlert("Copied", 'success');
  }

  render() {
    return (
      <Dialog className='TextViewDialog'
              onClose={() => {
                this.props.onClose();
              }}
              width={900}
              height={600}
              title={this.state.title}
              enableResizing
      >
        {this.makeControls()}
        <div className="PreviewBoxContent selectable">
          <pre>
            {this.state.text}
          </pre>
        </div>

      </Dialog>
    );
  }
}
