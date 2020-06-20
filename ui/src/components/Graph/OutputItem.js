import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { PLynxApi } from '../../API';
import Icon from '../Common/Icon';
import { PluginsConsumer } from '../../contexts';
import { API_ENDPOINT } from '../../configConsts';
import './OutputItem.css';

const FileDownload = require('react-file-download');

export default class OutputItem extends Component {
  download() {
    // TODO render multiple values if it is an array
    const resourceId = this.props.item.values[0];
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
    return (
      <div className='OutputItem'>
        <div className='OutputNameCell'>

          <div className="OutputItemPreview"
            onClick={() => this.handleClick()}>
            <PluginsConsumer>
            {
                plugins_dict => <Icon
                  type_descriptor={plugins_dict.resources_dict[this.props.item.file_type]}
                />
            }
            </PluginsConsumer>
            {this.props.item.name}
          </div>
        </div>
        <div className='OutputValueCell' onClick={() => {
          this.download();
        }}>
          <img src="/icons/download.svg" alt="download" /> {this.props.item.values[0]}
        </div>
      </div>
    );
  }
}

OutputItem.propTypes = {
  fileType: PropTypes.string,
  resourceId: PropTypes.string,
  resourceName: PropTypes.string,
  onPreview: PropTypes.func.isRequired,
  item: PropTypes.shape({
    values: PropTypes.array.isRequired,
    file_type: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
  }),
};
