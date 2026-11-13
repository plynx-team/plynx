import React, { Component, ReactNode } from 'react';
import MuiDialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import Typography from '@mui/material/Typography';
import PaperComponent from './DraggableComponent';
import './Dialog.css';

export interface DialogProps {
  children: ReactNode;
  enableResizing?: boolean;
  height?: number;
  onClose: () => void;
  title: string;
  width?: number;
  className?: string;
  defaultX?: number;
  defaultY?: number;
}

export default class Dialog extends Component<DialogProps> {
  render() {
    const { title, onClose, children, className, width, height } = this.props;

    return (
      <MuiDialog
        open
        onClose={onClose}
        PaperComponent={PaperComponent}
        aria-labelledby="draggable-dialog-title"
        maxWidth={false}
        PaperProps={{
          sx: {
            width: width ? `${width}px` : 'auto',
            minWidth: 320,
            maxWidth: '92vw',
            height: height ? `${height}px` : 'auto',
            maxHeight: '92vh',
            backgroundColor: '#2b2b2b',
            color: '#fff',
            borderRadius: '6px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45)',
          },
        }}
      >
        <DialogTitle
          id="draggable-dialog-title"
          sx={{
            cursor: 'move',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: '#202020',
            padding: '10px 16px',
            borderBottom: '1px solid #383838',
            userSelect: 'none',
          }}
        >
          <Typography variant="subtitle1" component="div" sx={{ fontWeight: 'var(--font-weight-semibold)', fontSize: 'var(--font-size-lg)', color: '#fff' }}>
            {title}
          </Typography>
          <IconButton
            aria-label="close"
            onClick={onClose}
            size="small"
            sx={{
              color: '#888',
              '&:hover': {
                color: '#fff',
                backgroundColor: 'rgba(255, 255, 255, 0.08)',
              },
            }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent
          className={className}
          sx={{
            padding: '16px',
            backgroundColor: '#2b2b2b',
            color: '#eee',
            fontSize: 'var(--font-size-base)',
            overflowY: 'auto',
          }}
        >
          {children}
        </DialogContent>
      </MuiDialog>
    );
  }
}
