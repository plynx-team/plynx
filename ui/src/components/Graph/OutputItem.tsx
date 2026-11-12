import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import Icon from '../Common/Icon';
import { PluginsConsumer } from '../../contexts';
import { API_ENDPOINT } from '../../configConsts';
import { downloadBlob } from '../../utils';
import { PreviewData, PluginsDict } from '../../types';
import './OutputItem.css';

export interface GraphOutputItemData {
  name: string;
  file_type: string;
  values: any[];
  [key: string]: any;
}

export interface GraphOutputItemProps {
  onPreview: (previewData: PreviewData) => void;
  item: GraphOutputItemData;
}

export default class OutputItem extends Component<GraphOutputItemProps> {
  download() {
    const resourceId = this.props.item.values[0];
    PLynxApi.endpoints.resource
      .getCustom({
        method: 'get',
        url: `${API_ENDPOINT}/resource/${resourceId}`,
        responseType: 'blob',
      })
      .then((response: any) => {
        downloadBlob(response.data, resourceId);
      })
      .catch((error: any) => {
        console.error(error);
      });
  }

  handleClick(displayRaw?: boolean) {
    if (this.props.onPreview) {
      this.props.onPreview({
        title: this.props.item.name,
        file_type: this.props.item.file_type,
        values: this.props.item.values,
        download_name: this.props.item.name,
        display_raw: displayRaw,
      });
    }
  }

  render() {
    return (
      <PluginsConsumer>
        {(plugins_dict: PluginsDict) => {
          const resourceDesc = plugins_dict.resources_dict[this.props.item.file_type];
          const displayRaw = resourceDesc ? resourceDesc.display_raw : false;

          return (
            <div className="OutputItem">
              <div className="OutputNameCell">
                <div
                  className="OutputItemPreview"
                  onClick={() => this.handleClick(displayRaw)}
                >
                  {resourceDesc && <Icon type_descriptor={resourceDesc} />}
                  {this.props.item.name}
                </div>
                {!displayRaw && (
                  <div
                    className="OutputValueCell"
                    onClick={() => {
                      this.download();
                    }}
                  >
                    <img src="/icons/download.svg" alt="download" /> {this.props.item.values[0]}
                  </div>
                )}
              </div>
            </div>
          );
        }}
      </PluginsConsumer>
    );
  }
}
