import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { PLynxApi } from '../../API';
import { API_ENDPOINT } from '../../configConsts';
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

  download() {
    const resourceId = this.props.resourceId;
    PLynxApi.endpoints.resource.getCustom({
      method: 'get',
      url: API_ENDPOINT + '/resource/' + resourceId,
      responseType: 'blob'
    })
      .then((response) => {
        console.log(response);
        FileDownload(response.data, resourceId);
      })
      .catch((error) => {
        console.error(error);
      });
  }

  handleClick() {
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
    // {{pathname: '/graphs/' + this.state.graphId, query: {node: this.state.nodeId, output_preview: this.state.resourceName}}}
    return (
      <div className='OutputItem'>
        <div className='OutputNameCell'>

          <div className="OutputItemPreview"
            onClick={() => this.handleClick()}>
            <img src="/icons/document.svg" alt="preview" /> {this.state.resourceName}
          </div>
        </div>
        <div className='OutputValueCell' onClick={() => {
          this.download();
        }}>
          <img src="/icons/download.svg" alt="download" /> {this.state.resourceId}
        </div>
      </div>
    );
  }
}

OutputItem.propTypes = {
  fileType: PropTypes.string,
  graphId: PropTypes.string,
  nodeId: PropTypes.string,
  resourceId: PropTypes.string,
  resourceName: PropTypes.string,
  onPreview: PropTypes.func,
};
