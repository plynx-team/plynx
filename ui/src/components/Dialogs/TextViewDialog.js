import React, { Component } from 'react';
import PropTypes from 'prop-types';
import PaperComponent from './DraggableComponent';

import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import { Button } from '@mui/material';
// import Box from '@mui/material/Box';

export default class TextViewDialog extends Component {
  static propTypes = {
    text: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    showAlert: PropTypes.func.isRequired,
    onClose: PropTypes.func.isRequired,
  };

  constructor(props) {
    super(props);
    this.state = {
      text: props.text,
      title: props.title
    };
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
      <Dialog
              onClose={() => {
                this.props.onClose();
              }}
              open
              scroll='paper'
              fullWidth
              PaperComponent={PaperComponent}
              aria-labelledby="draggable-dialog-title"
              aria-describedby="scroll-dialog-description"
      >
        <DialogTitle className='mui-dialog-title'>{this.state.title}</DialogTitle>
        <DialogContent
          sx={{
            padding: "0px",
            margin: "3px",
            borderRadius: "10px",
            backgroundColor: "#333",
          }}
        >
          <DialogContentText>
            <pre>
              {this.state.text}
            </pre>
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              this.handleCopy();
            }}
            color="primary"
          >
            Copy
          </Button>
          <Button
            onClick={() => {
              this.props.onClose();
            }}
            color="error"
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    );
  }
}
