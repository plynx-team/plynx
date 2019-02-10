// src/components/NotFound/index.js
import React, { Component } from 'react';
import Dialog from './Dialog.js'
import { PLynxApi } from '../../API.js';
import { FILE_STATUS, FILE_TYPES } from '../../constants.js'
import { API_ENDPOINT } from '../../configConsts.js';

const FileDownload = require('react-file-download');


export default class FileDialog extends Component {

  handlePreviewClick (e) {
    e.preventDefault();
    if (this.props.onPreview) {
      this.props.onPreview({
        title: this.props.fileObj.title,
        file_type: this.props.fileObj.outputs[0].file_type,
        resource_id: this.props.fileObj.outputs[0].resource_id,
        download_name: this.props.fileObj.title,
      });
    }
  }

  download() {
    var resourceId = this.props.fileObj.outputs[0].resource_id;
    var filename = this.props.fileObj.title;
    PLynxApi.endpoints.resource.getCustom({
        method: 'get',
        url: API_ENDPOINT + '/resource/' + resourceId,
        responseType: 'blob'
      })
      .then(function (response) {
        FileDownload(response.data, filename);
      })
      .catch(function (error) {
        console.error(error);
      });
  }

  render() {
    var typeTuple = FILE_TYPES.filter(
      (ft) => {return ft.type === this.props.fileObj.outputs[0].file_type}
    )[0];

    return (
      <Dialog className='FileDialog'
              onClose={() => {this.props.onClose()}}
              width={600}
              height={200}
              title={'File'}
              enableResizing={false}
      >
        <div className='FileDialogBody selectable'>
          <div className='MainBlock'>

            <div className='TitleDescription'>
              <div className='Title'>
                {this.props.fileObj.title}
              </div>
              <div className='Description'>
                &ldquo;{this.props.fileObj.description}&rdquo;
              </div>
            </div>

            <div className={'Type'}>
              <div className='Widget'>
                <img src={"/icons/file_types/" + typeTuple.type + ".svg"} alt={typeTuple.type} width="20" height="20" />
                {typeTuple.alias}
              </div>
            </div>

          </div>

          <div className='Summary'>
            <div className='Item'>
              <div className={'Name'}>Id:</div>
              <div className={'Id'}>{this.props.fileObj.parent_node || this.props.fileObj._id}</div>
            </div>

            <div className='Item'>
              <div className={'Name'}>Status:</div>
              <div className={'Status ' + this.props.fileObj.node_status}>{this.props.fileObj.node_status}</div>
            </div>

            <div className='Item'>
              <div className={'Name'}>Created:</div>
              <div className='Created'>{this.props.fileObj.insertion_date}</div>
            </div>
          </div>
          <div className='Controls'>
            <a href={null}
               onClick={(e) => this.handlePreviewClick(e) }
               className="control-button">
               <img src="/icons/preview.svg" alt="preview" /> Preview
            </a>
            <a href={null}
               onClick={(e) => {e.preventDefault(); this.download()}}
               className="control-button">
               <img src="/icons/download2.svg" alt="download" /> Download
            </a>
            { this.props.fileObj.node_status === FILE_STATUS.READY && !this.props.hideDeprecate &&
              <a href={null}
                 onClick={(e) => {e.preventDefault(); this.props.onDeprecate(this.props.fileObj); this.props.onClose();}}
                 className="control-button">
                 <img src="/icons/x.svg" alt="deprecate" /> Deprecate
              </a>
            }
          </div>
        </div>
      </Dialog>
    );
  }
}
