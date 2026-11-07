import React, { Component } from 'react';
import PropTypes from 'prop-types';
import LoadingScreen from '../LoadingScreen';
import { PLynxApi } from '../../API';
import { API_ENDPOINT } from '../../configConsts';
import { downloadBlob } from '../../utils';
import PaperComponent from './DraggableComponent';

import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';

import './PreviewDialog.css';

export default class PreviewDialog extends Component {
  static propTypes = {
    title: PropTypes.string.isRequired,
    values: PropTypes.array,
    resource_id: PropTypes.string,
    display_raw: PropTypes.bool,
    download_name: PropTypes.string.isRequired,
    file_type: PropTypes.string.isRequired,
    onClose: PropTypes.func.isRequired,
  };

  constructor(props) {
    super(props);
    const values = props.values || (props.resource_id ? [props.resource_id] : []);
    const displayRaw = Boolean(props.display_raw);
    this.state = {
      title: props.title,
      file_type: props.file_type,
      values: values,
      display_raw: displayRaw,
      download_name: props.download_name,
      content: displayRaw ? values : '',
      loading: !displayRaw,
    };
  }

  componentDidMount() {
    if (!this.state.display_raw && this.state.values.length > 0) {
      PLynxApi.endpoints.resource
        .getCustom({
          method: 'get',
          // Hack: "?"... is needed for live logs. Otherwise the result is cached and logs do not update
          url: `${API_ENDPOINT}/resource/${this.state.values[0]}?${Math.random()}`,
          params: {
            preview: true,
            file_type: this.state.file_type,
          },
        })
        .then((response) => {
          this.setState({
            content: response.data,
            loading: false,
          });
        })
        .catch((error) => {
          console.error(error);
          this.setState({
            content: String(error),
            loading: false,
          });
        });
    }
  }

  download(resource_id, download_name) {
    PLynxApi.endpoints.resource
      .getCustom({
        method: 'get',
        url: `${API_ENDPOINT}/resource/${resource_id}`,
        responseType: 'blob',
      })
      .then((response) => {
        downloadBlob(response.data, download_name || resource_id);
      })
      .catch((error) => {
        console.error(error);
      });
  }

  previewMessage(resource_id, download_name) {
    return (
      <div className="note">
        {'This is a preview and might not the entire file. You can download the entire file here:'}
        <div
          className="preview-download-link"
          onClick={() => {
            this.download(resource_id, download_name);
          }}
        >
          <img src="/icons/download.svg" alt="download" /> {resource_id}
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
            {!this.state.display_raw && this.previewMessage(this.state.values[0], this.state.download_name)}
            <div
              dangerouslySetInnerHTML={{ __html: this.state.content }}  
            />
          </div>
        </DialogContent>
      </Dialog>
    );
  }
}
