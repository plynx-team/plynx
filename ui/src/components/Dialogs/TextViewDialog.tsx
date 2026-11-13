import React, { Component } from 'react';
import PaperComponent from './DraggableComponent';

import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import { Button } from '@mui/material';

export interface TextViewDialogProps {
  text: string;
  title: string;
  showAlert: (message: string, type: string) => void;
  onClose: () => void;
  className?: string;
}

interface TextViewDialogState {
  text: string;
  title: string;
}

export default class TextViewDialog extends Component<TextViewDialogProps, TextViewDialogState> {
  constructor(props: TextViewDialogProps) {
    super(props);
    this.state = {
      text: props.text,
      title: props.title,
    };
  }

  handleCopy() {
    const copyText = this.state.text;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(copyText);
    } else {
      const textArea = document.createElement('textarea');
      textArea.textContent = copyText;
      document.body.append(textArea);
      textArea.select();
      document.execCommand('copy');
      textArea.remove();
    }
    this.props.showAlert('Copied to clipboard', 'success');
  }

  render() {
    return (
      <Dialog
        open
        onClose={this.props.onClose}
        PaperComponent={PaperComponent}
        aria-labelledby="draggable-dialog-title"
        maxWidth="md"
        fullWidth
      >
        <DialogTitle style={{ cursor: 'move' }} id="draggable-dialog-title">
          {this.state.title}
        </DialogTitle>
        <DialogContent>
          <DialogContentText
            component="pre"
            sx={{
              color: '#eee',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--font-size-base)',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              backgroundColor: '#262626',
              padding: 2,
              borderRadius: 1,
            }}
          >
            {this.state.text}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => this.handleCopy()} color="primary">
            Copy
          </Button>
          <Button onClick={this.props.onClose} color="inherit">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    );
  }
}
