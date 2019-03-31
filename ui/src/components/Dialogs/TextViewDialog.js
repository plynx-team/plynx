import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Dialog from './Dialog';


export default class TextViewDialog extends Component {
  static propTypes = {
    text: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    onClose: PropTypes.func.isRequired,
  }

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
              onClose={() => {
                this.props.onClose();
              }}
              width={900}
              height={600}
              title={this.state.title}
              enableResizing
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
