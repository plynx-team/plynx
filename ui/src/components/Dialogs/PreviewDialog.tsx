import React, { Component } from 'react';
import LoadingScreen from '../LoadingScreen';
import { PLynxApi } from '../../api';
import { API_ENDPOINT } from '../../config';
import { downloadBlob } from '../../utils';
import Dialog from './Dialog';
import { PreviewData } from '../../types';

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
    const isArray = Boolean(props.is_array);

    let initialContent = '';
    if (displayRaw) {
      let targetValue: any = values;
      // In Plynx data model, Output.values is always a List[Any].
      // When is_array is false, unbox the singular value from values[0].
      if (!isArray && Array.isArray(values) && values.length === 1) {
        targetValue = values[0];
      }

      if (typeof targetValue === 'string') {
        initialContent = targetValue;
      } else if (typeof targetValue === 'number' || typeof targetValue === 'boolean') {
        initialContent = String(targetValue);
      } else if (targetValue !== undefined && targetValue !== null) {
        try {
          initialContent = JSON.stringify(targetValue, null, 2);
        } catch {
          initialContent = String(targetValue);
        }
      }
    }

    this.state = {
      title: props.title,
      file_type: props.file_type,
      values,
      display_raw: displayRaw,
      download_name: downloadName,
      content: initialContent,
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
      <div className="preview-note-banner">
        <div className="preview-note-text">
          This is a preview and might not be the entire file. You can download the entire file here:
        </div>
        <div
          className="preview-download-button"
          onClick={() => {
            this.download(resourceId, downloadName);
          }}
          role="button"
          tabIndex={0}
        >
          <img src="/icons/download.svg" alt="download" />
          <span>{downloadName || resourceId}</span>
        </div>
      </div>
    );
  }

  render() {
    return (
      <Dialog
        className="PreviewDialogWindow"
        onClose={() => {
          this.props.onClose();
        }}
        width={640}
        title={this.state.title}
        contentPadding={0}
      >
        {this.state.loading && (
          <div className="LoadHolder">
            <LoadingScreen />
          </div>
        )}
        {!this.state.display_raw && this.state.values.length > 0 &&
          this.previewMessage(this.state.values[0], this.state.download_name)}
        <div className="preview-content-box selectable">
          {this.state.display_raw ? (
            <pre className="preview-code-block">{this.state.content}</pre>
          ) : (
            <div
              className="preview-code-block"
              dangerouslySetInnerHTML={{ __html: this.state.content }}
            />
          )}
        </div>
      </Dialog>
    );
  }
}
