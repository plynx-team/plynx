import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Dialog from './Dialog';
import LoadingScreen from '../LoadingScreen';
import { PLynxApi } from '../../API';
import { API_ENDPOINT } from '../../configConsts';
import './PreviewDialog.css';

const FileDownload = require('react-file-download');

export default class PreviewDialog extends Component {
  static propTypes = {
    title: PropTypes.string.isRequired,
    values: PropTypes.array.isRequired,
    display_raw: PropTypes.bool.isRequired,
    download_name: PropTypes.string.isRequired,
    file_type: PropTypes.string.isRequired,
    onClose: PropTypes.func.isRequired,
  };

  constructor(props) {
    super(props);
    this.state = {
      title: props.title,
      file_type: props.file_type,
      values: props.values,
      display_raw: props.display_raw,
      download_name: props.download_name,
      content: "",
      loading: true
    };

    if (!props.display_raw) {
      const self = this;
      PLynxApi.endpoints.resource.getCustom({
        method: 'get',
          // Hack: "?"... is needed for life logs. Otherwise the result is cached and logs do not update
        url: API_ENDPOINT + '/resource/' + props.values[0] + '?' + Math.random(),
        params: {
          preview: true,
          file_type: props.file_type,
        },
      }).then((response) => {
        self.setState({
          content: response.data,
          loading: false
        });
      })
          .catch((error) => {
            console.error(error);
            self.setState({
              content: error,
              loading: false
            });
          });
    } else {
      this.state.content = props.values;
      this.state.loading = false;
    }
  }

  download(resource_id, download_name) {
    PLynxApi.endpoints.resource.getCustom({
      method: 'get',
      url: API_ENDPOINT + '/resource/' + resource_id,
      responseType: 'blob'
    })
      .then((response) => {
        FileDownload(response.data, resource_id, download_name);
      })
      .catch((error) => {
        console.error(error);
      });
  }

  previewMessage(resource_id) {
    return (
      <div className="note">
         {'This is a preview and might not the entire file. You can download the entire file here:'}
         <div className="preview-download-link" onClick={() => {
           this.download(resource_id);
         }}>
           <img src="/icons/download.svg" alt="download" /> {resource_id}
         </div>
      </div>
    );
  }

  render() {
    return (
      <Dialog className='FileDialog'
              onClose={() => {
                this.props.onClose();
              }}
              width={900}
              height={700}
              title={this.state.title}
              enableResizing
      >
        {this.state.loading &&
          <div className='LoadHolder'>
            <LoadingScreen />
          </div>
        }
        <div className="PreviewBoxContent selectable">
          <div>
            {!this.state.display_raw && this.previewMessage(this.state.values[0], this.state.download_name)}
            <div
              dangerouslySetInnerHTML={{ __html: this.state.content }}           // eslint-disable-line react/no-danger
            />
          </div>
        </div>

      </Dialog>
    );
  }
}
