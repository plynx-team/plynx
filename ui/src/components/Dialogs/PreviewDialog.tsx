import React, { Component } from 'react';
import LoadingScreen from '../LoadingScreen';
import { PLynxApi } from '../../API';
import { API_ENDPOINT } from '../../configConsts';
import { downloadBlob } from '../../utils';
import PaperComponent from './DraggableComponent';
import { PreviewData } from '../../types';

import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';

import './PreviewDialog.css';

export interface PreviewDialogProps extends Partial<PreviewData> {
  title: string;
  file_type: string;
  download_name?: string;
  onClose: () => void;
  className?: string;
}

interface PreviewDialogState {
  title: string;
  file_type: string;
  values: any[];
  display_raw: boolean;
  download_name: string;
  content: string;
  loading: boolean;
}

export default class PreviewDialog extends Component<PreviewDialogProps, PreviewDialogState> {
  constructor(props: PreviewDialogProps) {
    super(props);
    const values = props.values || (props.resource_id ? [props.resource_id] : []);
    const displayRaw = Boolean(props.display_raw);
    const downloadName = props.download_name || props.title;
    this.state = {
      title: props.title,
      file_type: props.file_type,
      values,
      display_raw: displayRaw,
      download_name: downloadName,
      content: displayRaw ? JSON.stringify(values) : '',
      loading: !displayRaw,
    };
  }

  componentDidMount() {
    if (!this.state.display_raw && this.state.values.length > 0) {
      PLynxApi.endpoints.resource
        .getCustom({
          method: 'get',
          url: `${API_ENDPOINT}/resource/${this.state.values[0]}?${Math.random()}`,
          params: {
            preview: true,
            file_type: this.state.file_type,
          },
        })
        .then((response: any) => {
          this.setState({
            content: response.data,
            loading: false,
          });
        })
        .catch((error: any) => {
          console.error(error);
          this.setState({
            content: String(error),
            loading: false,
          });
        });
    }
  }

  download(resourceId: string, downloadName: string) {
    PLynxApi.endpoints.resource
      .getCustom({
        method: 'get',
        url: `${API_ENDPOINT}/resource/${resourceId}`,
        responseType: 'blob',
      })
      .then((response: any) => {
        downloadBlob(response.data, downloadName || resourceId);
      })
      .catch((error: any) => {
        console.error(error);
      });
  }

  previewMessage(resourceId: string, downloadName: string) {
    return (
      <div className="note">
        {'This is a preview and might not the entire file. You can download the entire file here:'}
        <div
          className="preview-download-link"
          onClick={() => {
            this.download(resourceId, downloadName);
          }}
        >
          <img src="/icons/download.svg" alt="download" /> {resourceId}
        </div>
      </div>
    );
  }

  render() {
    return (
      <Dialog
        className="FileDialog"
        onClose={() => {
          this.props.onClose();
        }}
        open
        scroll="paper"
        fullWidth
        PaperComponent={PaperComponent}
        aria-labelledby="draggable-dialog-title"
        aria-describedby="scroll-dialog-description"
      >
        {this.state.loading && (
          <div className="LoadHolder">
            <LoadingScreen />
          </div>
        )}
        <DialogTitle id="draggable-dialog-title" className="mui-dialog-title">
          {this.state.title}
        </DialogTitle>
        <DialogContent
          sx={{
            padding: '0px',
            margin: '3px',
            borderRadius: '10px',
            backgroundColor: '#333',
          }}
        >
          <div>
            {!this.state.display_raw && this.state.values.length > 0 &&
              this.previewMessage(this.state.values[0], this.state.download_name)}
            <div dangerouslySetInnerHTML={{ __html: this.state.content }} />
          </div>
        </DialogContent>
      </Dialog>
    );
  }
}
