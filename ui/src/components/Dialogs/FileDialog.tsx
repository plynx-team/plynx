import React, { Component, MouseEvent } from 'react';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Dialog from './Dialog';
import { PLynxApi } from '../../API';
import { PluginsConsumer } from '../../contexts';
import Icon from '../Common/Icon';
import { NODE_STATUS } from '../../constants';
import { API_ENDPOINT } from '../../configConsts';
import { downloadBlob } from '../../utils';
import { PreviewData, PluginsDict } from '../../types';

export interface FileObject {
  _id: string;
  title: string;
  description: string;
  insertion_date?: string;
  node_status: string;
  original_node_id?: string;
  outputs: Array<{
    file_type: string;
    resource_id: string;
    [key: string]: any;
  }>;
}

export interface FileDialogProps {
  fileObj: FileObject;
  hideDeprecate: boolean;
  onClose: () => void;
  onDeprecate: (fileObj: FileObject) => void;
  onPreview: (data: PreviewData) => void;
}

export default class FileDialog extends Component<FileDialogProps> {
  handlePreviewClick(e: MouseEvent<any>) {
    e.preventDefault();
    if (this.props.onPreview && this.props.fileObj.outputs[0]) {
      this.props.onPreview({
        title: this.props.fileObj.title,
        file_type: this.props.fileObj.outputs[0].file_type,
        resource_id: this.props.fileObj.outputs[0].resource_id,
        download_name: this.props.fileObj.title,
      });
    }
  }

  download() {
    if (!this.props.fileObj.outputs[0]) return;
    const resourceId = this.props.fileObj.outputs[0].resource_id;
    const filename = this.props.fileObj.title;
    PLynxApi.endpoints.resource
      .getCustom({
        method: 'get',
        url: `${API_ENDPOINT}/resource/${resourceId}`,
        responseType: 'blob',
      })
      .then((response: any) => {
        downloadBlob(response.data, filename);
      })
      .catch((error: any) => {
        console.error(error);
      });
  }

  render() {
    const { fileObj } = this.props;
    const firstOutput = fileObj.outputs && fileObj.outputs[0];

    return (
      <Dialog
        className="FileDialog"
        onClose={() => {
          this.props.onClose();
        }}
        width={600}
        height={200}
        title="File"
        enableResizing={false}
      >
        <div className="FileDialogBody selectable">
          <div className="MainBlock">
            <div className="TitleDescription">
              <div className="Title">{fileObj.title}</div>
              <div className="Description">&ldquo;{fileObj.description}&rdquo;</div>
            </div>

            {firstOutput && (
              <PluginsConsumer>
                {(plugins_dict: PluginsDict) => {
                  const resourceDesc = plugins_dict.resources_dict[firstOutput.file_type];
                  return (
                    <div className="Type">
                      <div className="Widget">
                        {resourceDesc && (
                          <Icon
                            type_descriptor={resourceDesc}
                            width="20"
                            height="20"
                          />
                        )}
                        {resourceDesc ? resourceDesc.alias : firstOutput.file_type}
                      </div>
                    </div>
                  );
                }}
              </PluginsConsumer>
            )}
          </div>

          <div className="Summary">
            <div className="Item">
              <div className="Name">Id:</div>
              <div className="Id">{fileObj.original_node_id || fileObj._id}</div>
            </div>

            <div className="Item">
              <div className="Name">Status:</div>
              <div className={`Status ${fileObj.node_status}`}>{fileObj.node_status}</div>
            </div>

            {fileObj.insertion_date && (
              <div className="Item">
                <div className="Name">Created:</div>
                <div className="Created">{fileObj.insertion_date}</div>
              </div>
            )}
          </div>
          <Stack direction="row" spacing={1.5} justifyContent="flex-end" sx={{ marginTop: 2 }}>
            <Button
              variant="contained"
              color="primary"
              size="small"
              startIcon={<img src="/icons/preview.svg" alt="preview" width="16" height="16" />}
              onClick={(e) => this.handlePreviewClick(e)}
              sx={{ textTransform: 'none' }}
            >
              Preview
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              size="small"
              startIcon={<img src="/icons/download2.svg" alt="download" width="16" height="16" />}
              onClick={(e) => {
                e.preventDefault();
                this.download();
              }}
              sx={{ textTransform: 'none', borderColor: '#555' }}
            >
              Download
            </Button>
            {fileObj.node_status === NODE_STATUS.READY && !this.props.hideDeprecate && (
              <Button
                variant="outlined"
                color="error"
                size="small"
                startIcon={<img src="/icons/x.svg" alt="deprecate" width="16" height="16" />}
                onClick={(e) => {
                  e.preventDefault();
                  this.props.onDeprecate(fileObj);
                  this.props.onClose();
                }}
                sx={{ textTransform: 'none' }}
              >
                Deprecate
              </Button>
            )}
          </Stack>
        </div>
      </Dialog>
    );
  }
}
