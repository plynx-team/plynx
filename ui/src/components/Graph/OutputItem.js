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

  handleClick(display_raw) {
    if (this.props.onPreview) {
      this.props.onPreview({
        title: this.props.item.name,
        file_type: this.props.item.file_type,
        values: this.props.item.values,
        download_name: this.props.item.name,
        display_raw: display_raw,
      });
    }
  }

  render() {
    return (
      <PluginsConsumer>
      {
        plugins_dict =>
      <div className='OutputItem'>
        <div className='OutputNameCell'>

          <div className="OutputItemPreview"
            onClick={() => this.handleClick(plugins_dict.resources_dict[this.props.item.file_type].display_raw)}>

                <Icon
                  type_descriptor={plugins_dict.resources_dict[this.props.item.file_type]}
                />
            {this.props.item.name}
          </div>
        {!plugins_dict.resources_dict[this.props.item.file_type].display_raw &&
        <div className='OutputValueCell' onClick={() => {
          this.download();
        }}>
          <img src="/icons/download.svg" alt="download" /> {this.props.item.values[0]}
        </div>
        }
      </div>
      </div>
      }
      </PluginsConsumer>
    );
  }
}

OutputItem.propTypes = {
  onPreview: PropTypes.func.isRequired,
  item: PropTypes.shape({
    values: PropTypes.array.isRequired,
    file_type: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
  }),
};
