import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { CsvToHtmlTable } from 'react-csv-to-table';
import Dialog from './Dialog';
import LoadingScreen from '../LoadingScreen';
import { PLynxApi } from '../../API';
import { API_ENDPOINT, CLOUD_STORAGE_PREFIX, CLOUD_STORAGE_POSTFIX } from '../../configConsts';
import './PreviewDialog.css';

const FileDownload = require('react-file-download');

const SPECIAL_PREVIEW_TYPES = ['image', 'pdf', 'cloud-storage', 'csv'];
const NON_TEXT_TYPES = ['image', 'pdf'];


export default class PreviewDialog extends Component {
  static propTypes = {
    title: PropTypes.string.isRequired,
    resource_id: PropTypes.string.isRequired,
    download_name: PropTypes.string.isRequired,
    file_type: PropTypes.string.isRequired,
    onClose: PropTypes.func.isRequired,
  }

  constructor(props) {
    super(props);
    const isText = NON_TEXT_TYPES.indexOf(props.file_type) < 0;
    this.state = {
      title: props.title,
      file_type: props.file_type,
      resource_id: props.resource_id,
      download_name: props.download_name,
      content: "",
      loading: isText
    };

    if (isText) {
      const self = this;
      PLynxApi.endpoints.resource.getCustom({
        method: 'get',
        // Hack: "?"... is needed for life logs. Otherwise the result is cached and logs do not update
        url: API_ENDPOINT + '/resource/' + props.resource_id + '?' + Math.random(),
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
         {'Please note it is preview and might not the entire file. You can download the entire file here:'}
         <div className="preview-download-link" onClick={() => {
           this.download(resource_id);
         }}>
           <img src="/icons/download_dark.svg" alt="download" /> {resource_id}
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
          { SPECIAL_PREVIEW_TYPES.indexOf(this.state.file_type) < 0 &&
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
               <p>This browser does not support PDFs. Please download the PDF to view it:
                <a href="/pdf/sample-3pp.pdf">Download PDF</a>
               </p>
            </iframe>
          }
          { this.state.file_type === 'image' &&
            <img src={API_ENDPOINT + '/resource/' + this.state.resource_id} width="100%" alt="preview" />
          }
          { this.state.file_type === 'cloud-storage' &&
            <div>
              {
                this.state.content.path &&
                <a href={CLOUD_STORAGE_PREFIX + this.state.content.path.split('//')[1] + CLOUD_STORAGE_POSTFIX}>{this.state.content.path}</a>
              }
            </div>
          }
          { (this.state.file_type === 'csv' || this.state.file_type === 'tsv') &&
            <div>
              {this.previewMessage(this.state.resource_id, this.state.download_name)}
              <CsvToHtmlTable
                data={this.state.content}
                csvDelimiter={this.state.file_type === 'tsv' ? "\t" : ","}
                tableClassName="preview-table"
                tableRowClassName="preview-table-row"
                tableColumnClassName="preview-table-col"
                hasHeader={false}
              />
            </div>
          }
        </div>

      </Dialog>
    );
  }
}
