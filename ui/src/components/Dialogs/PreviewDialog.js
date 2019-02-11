// src/components/About/index.js
import React, { Component } from 'react';
import Dialog from './Dialog.js'
import LoadingScreen from '../LoadingScreen.js'
import { PLynxApi } from '../../API.js';
import { API_ENDPOINT } from '../../configConsts.js';

const FileDownload = require('react-file-download');

export default class PreviewDialog extends Component {
  constructor(props) {
    super(props);
    var isText = (props.file_type !== 'image' && props.file_type !== 'pdf');
    this.state = {
      title: props.title,
      file_type: props.file_type,
      resource_id: props.resource_id,
      download_name: props.download_name,
      content: "",
      loading: isText
    };

    if (isText) {
      var self = this;
      PLynxApi.endpoints.resource.getCustom({
          method: 'get',
          url: API_ENDPOINT + '/resource/' + props.resource_id,
          params: {
            preview: true,
            file_type: props.file_type,
          },
        }).then(function (response) {
          self.setState({
            content: response.data,
            loading: false
          });
        })
        .catch(function (error) {
          console.error(error);
          self.setState({
            content: error,
            loading: false
          });
        });
    }
  }

  download(resource_id, download_name) {
    PLynxApi.endpoints.resource.getCustom({
        method: 'get',
        url: API_ENDPOINT + '/resource/' + resource_id,
        responseType: 'blob'
      })
      .then(function (response) {
        FileDownload(response.data, resource_id, download_name);
      })
      .catch(function (error) {
        console.error(error);
      });
  }

  previewMessage(resource_id) {
    return (
      <div className="note">
         {'Please note it is preview and might not the entire file. You can download the entire file here:'}
         <div className="preview-download-link" onClick={(e) => {this.download(resource_id)}}>
           <img src="/icons/download_dark.svg" alt="download" /> {resource_id}
         </div>
      </div>
    );
  }


  render() {
    return (
      <Dialog className='FileDialog'
              onClose={() => {this.props.onClose()}}
              width={900}
              height={700}
              title={this.state.title}
              enableResizing={true}
      >
        {this.state.loading &&
          <div className='LoadHolder'>
            <LoadingScreen />
          </div>
        }
        <div className="PreviewBoxContent">
          { ['executable', 'file', 'tsv', 'csv', 'json', 'directory'].indexOf(this.state.file_type) > -1 &&
            <div>
              {this.previewMessage(this.state.resource_id, this.state.download_name)}
              <pre>
                {this.state.content}
              </pre>
            </div>
          }
          { this.state.file_type === 'pdf' &&
            <iframe
              src={API_ENDPOINT + '/resource/' + this.state.resource_id}
              title="preview"
              type="application/pdf"
              width="100%"
              height="100%"
              >
               <p><b>Example fallback content</b>: This browser does not support PDFs. Please download the PDF to view it: <a href="/pdf/sample-3pp.pdf">Download PDF</a>.</p>
            </iframe>
          }
          { this.state.file_type === 'image' &&
            <img src={API_ENDPOINT + '/resource/' + this.state.resource_id} width="100%" alt="preview" />
          }
        </div>

      </Dialog>
    );
  }
}
