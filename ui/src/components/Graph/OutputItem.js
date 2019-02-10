// src/components/About/index.js
import React, { Component } from 'react';
import { PLynxApi } from '../../API.js';
import { API_ENDPOINT } from '../../configConsts.js';
import './OutputItem.css';

const FileDownload = require('react-file-download');

export default class OutputItem extends Component {
  constructor(props) {
    super(props);
    this.state = {
      resourceName: this.props.resourceName,
      resourceId: this.props.resourceId,
      graphId: this.props.graphId,
      nodeId: this.props.nodeId,
    };
  }

  download(e) {
    var resourceId = this.props.resourceId;
    PLynxApi.endpoints.resource.getCustom({
        method: 'get',
        url: API_ENDPOINT + '/resource/' + resourceId,
        responseType: 'blob'
      })
      .then(function (response) {
        console.log(response);
        FileDownload(response.data, resourceId);
      })
      .catch(function (error) {
        console.error(error);
      });
  }

  handleClick(e) {
    if (this.props.onPreview) {
      this.props.onPreview({
        title: this.props.resourceName,
        file_type: this.props.fileType,
        resource_id: this.props.resourceId,
        download_name: this.props.resourceName,
      });
    }
  }

  render() {
    //{{pathname: '/graphs/' + this.state.graphId, query: {node: this.state.nodeId, output_preview: this.state.resourceName}}}
    return (
      <div className='OutputItem'>
        <div className='OutputNameCell'>

          <div className="OutputItemPreview"
            onClick={(e) => this.handleClick(e)}>
            <img src="/icons/document.svg" alt="preview" /> {this.state.resourceName}
          </div>
        </div>
        <div className='OutputValueCell' onClick={(e) => {this.download(e)}}>
          <img src="/icons/download.svg" alt="download" /> {this.state.resourceId}
        </div>
      </div>
    );
  }
}
