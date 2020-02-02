import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Dialog from './Dialog';
import { PLynxApi } from '../../API';
import {PluginsConsumer} from '../../contexts';
import Icon from '../Common/Icon';
import { FILE_STATUS, NODE_STATUS } from '../../constants';
import { API_ENDPOINT } from '../../configConsts';

const FileDownload = require('react-file-download');


export default class FileDialog extends Component {
  static propTypes = {
    fileObj: PropTypes.shape({
      _id: PropTypes.string.isRequired,
      title: PropTypes.string.isRequired,
      description: PropTypes.string.isRequired,
      insertion_date: PropTypes.string,
      node_status: PropTypes.oneOf(Object.values(NODE_STATUS)).isRequired,
      original_node_id: PropTypes.string,
      outputs: PropTypes.array.isRequired,
    }),
    hideDeprecate: PropTypes.bool.isRequired,
    onClose: PropTypes.func.isRequired,
    onDeprecate: PropTypes.func.isRequired,
    onPreview: PropTypes.func.isRequired,
  }

  handlePreviewClick(e) {
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
    const resourceId = this.props.fileObj.outputs[0].resource_id;
    const filename = this.props.fileObj.title;
    PLynxApi.endpoints.resource.getCustom({
      method: 'get',
      url: API_ENDPOINT + '/resource/' + resourceId,
      responseType: 'blob'
    })
      .then((response) => {
        FileDownload(response.data, filename);
      })
      .catch((error) => {
        console.error(error);
      });
  }

  render() {
    return (
      <Dialog className='FileDialog'
              onClose={() => {
                this.props.onClose();
              }}
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

            <PluginsConsumer>
            { plugins_dict => <div className={'Type'}>
                <div className='Widget'>
                  <Icon
                    type_descriptor={plugins_dict.resources_dict[this.props.fileObj.outputs[0].file_type]}
                    width={"20"}
                    height={"20"}
                  />
                  {plugins_dict.resources_dict[this.props.fileObj.outputs[0].file_type].alias}
                </div>
              </div>
            }
            </PluginsConsumer>

          </div>

          <div className='Summary'>
            <div className='Item'>
              <div className={'Name'}>Id:</div>
              <div className={'Id'}>{this.props.fileObj.original_node_id || this.props.fileObj._id}</div>
            </div>

            <div className='Item'>
              <div className={'Name'}>Status:</div>
              <div className={'Status ' + this.props.fileObj.node_status}>{this.props.fileObj.node_status}</div>
            </div>

            {this.props.fileObj.insertion_date &&
              <div className='Item'>
                <div className={'Name'}>Created:</div>
                <div className='Created'>{this.props.fileObj.insertion_date}</div>
              </div>
            }
          </div>
          <div className='Controls'>
            <div
               onClick={(e) => this.handlePreviewClick(e)}
               className="control-button">
               <img src="/icons/preview.svg" alt="preview" /> Preview
            </div>
            <div
               onClick={(e) => {
                 e.preventDefault();
                 this.download();
               }}
               className="control-button">
               <img src="/icons/download2.svg" alt="download" /> Download
            </div>
            { this.props.fileObj.node_status === FILE_STATUS.READY && !this.props.hideDeprecate &&
              <div
                 onClick={(e) => {
                   e.preventDefault();
                   this.props.onDeprecate(this.props.fileObj);
                   this.props.onClose();
                 }}
                 className="control-button">
                 <img src="/icons/x.svg" alt="deprecate" /> Deprecate
              </div>
            }
          </div>
        </div>
      </Dialog>
    );
  }
}
