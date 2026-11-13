import React, { Component, ChangeEvent } from 'react';
import { PLynxApi } from '../../api';
import LoadingScreen from '../LoadingScreen';
import Icon from '../Common/Icon';
import { RESPONCE_STATUS } from '../../constants';
import PaperComponent from './DraggableComponent';
import { PluginsDict } from '../../types';
import './FileUploadDialog.css';

import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import MenuItem from '@mui/material/MenuItem';
import InputLabel from '@mui/material/InputLabel';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Select from '@mui/material/Select';

import { StyledListItemIcon } from '../Common/MuiComponents';

import FileUploadIcon from '@mui/icons-material/FileUpload';
import FileOpenIcon from '@mui/icons-material/FileOpen';

import { FormControl } from '@mui/material';

const DEFAULT_TITLE = 'File';

export interface UploadResource {
  kind: string;
  title: string;
  extensions: string[];
}

export interface UploadOperation {
  kind: string;
  resources: UploadResource[];
}

export interface FileUploadDialogProps {
  onClose: () => void;
  uploadOperation: UploadOperation;
  plugins_info: PluginsDict;
  onUpload?: (node: any) => void;
  doNotSave?: boolean;
  showAlert?: (message: string, type: string) => void;
}

interface FileUploadDialogState {
  title: string;
  description: string;
  file_type: string;
  file_path: File | null;
  file_name: string | null;
  uploadProgress: number;
  loading: boolean;
}

export default class FileUploadDialog extends Component<FileUploadDialogProps, FileUploadDialogState> {
  file: File | null = null;
  uploadDialog: HTMLInputElement | null = null;

  constructor(props: FileUploadDialogProps) {
    super(props);
    const op = props.plugins_info.operations_dict?.[props.uploadOperation.kind];
    const initialFileType =
      op?.resources?.[0]?.kind ||
      props.uploadOperation.resources?.[0]?.kind ||
      '';

    this.state = {
      title: DEFAULT_TITLE,
      description: '',
      file_type: initialFileType,
      file_path: null,
      file_name: null,
      uploadProgress: 10,
      loading: false,
    };
  }

  handleChange(event: any) {
    const name = event.target.name;
    const value = event.target.value;

    this.setState({
      [name]: value,
    } as any);

    if (name === 'file-dialog' && event.target.files) {
      this.file = event.target.files[0];
      if (this.file && this.file.name) {
        const extension = (this.file.name.split('.').pop() || '').toUpperCase();

        for (const resource of this.props.uploadOperation.resources) {
          if (resource.extensions.map((st) => st.toUpperCase()).includes(extension)) {
            this.setState({ file_type: resource.kind });
          }
        }
      }

      this.setState({
        file_path: this.file,
        file_name: this.file ? this.file.name : null,
        title: this.file && this.state.title === DEFAULT_TITLE ? this.file.name : this.state.title,
      });
    }
  }

  handleChooseFile() {
    if (this.uploadDialog) {
      this.uploadDialog.click();
    }
  }

  upload(retryCount: number) {
    const formData = new FormData();
    if (this.file) {
      formData.append('data', this.file);
    }
    formData.append('title', this.state.title);
    formData.append('description', this.state.description);
    formData.append('file_type', this.state.file_type);
    formData.append('node_kind', this.props.uploadOperation.kind);
    formData.append('do_not_save', String(Boolean(this.props.doNotSave)));

    const config = {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: any) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
        this.setState({
          uploadProgress: percentCompleted,
        });
      },
    };

    this.setState({ loading: true });
    PLynxApi.endpoints.upload_file
      .upload(formData, config)
      .then((response: any) => {
        const data = response.data;

        if (data.status === RESPONCE_STATUS.SUCCESS) {
          this.props.onClose();
          this.setState({ loading: false });
        }
        if (this.props.onUpload) {
          this.props.onUpload(data.node);
        }
      })
      .catch((error: any) => {
        console.error('error', error);

        if (error.response && error.response.status === 401) {
          PLynxApi.getAccessToken().then((isSuccessfull) => {
            if (!isSuccessfull) {
              console.error('Could not refresh token');
            } else if (retryCount > 0) {
              this.upload(retryCount - 1);
              return;
            }
          });
        } else if (this.props.showAlert) {
          this.props.showAlert('Failed to upload file. Did you choose the right file type?', 'failed');
        }
        this.setState({ loading: false });
      });
  }

  render() {
    return (
      <Dialog
        className="mui-dialog"
        open
        onClose={() => {
          this.props.onClose();
        }}
        aria-labelledby="draggable-dialog-title"
        aria-describedby="scroll-dialog-description"
        fullWidth
        PaperComponent={PaperComponent}
      >
        <DialogTitle id="draggable-dialog-title" className="mui-dialog-title">
          Upload a File
        </DialogTitle>
        {this.state.loading && (
          <div className="LoadHolder">
            <LoadingScreen />
          </div>
        )}
        <DialogContent className="mui-dialog-content">
          <div className="mui-dialog-file-upload">
            <TextField
              id="standard-basic"
              label="Title"
              variant="outlined"
              value={this.state.title}
              name="title"
              onChange={(e) => this.handleChange(e)}
              error={this.state.title === ''}
              className="mui-text-field"
            />

            <TextField
              id="standard-basic"
              label="Description"
              variant="outlined"
              value={this.state.description}
              name="description"
              onChange={(e) => this.handleChange(e)}
              className="mui-text-field"
            />

            <FormControl fullWidth>
              <InputLabel id="demo-simple-select-label">File type</InputLabel>
              <Select
                labelId="demo-simple-select-label"
                id="demo-simple-select"
                label="File type"
                name="file_type"
                value={this.state.file_type}
                onChange={(e) => this.handleChange(e)}
              >
                {Object.values(this.props.uploadOperation.resources).map((description) => {
                  const resourceDesc = this.props.plugins_info.resources_dict[description.kind];
                  return (
                    <MenuItem value={description.kind} key={description.kind}>
                      <StyledListItemIcon>
                        {resourceDesc && (
                          <Icon
                            type_descriptor={resourceDesc}
                            width="20"
                            height="20"
                          />
                        )}
                      </StyledListItemIcon>
                      {description.title}
                    </MenuItem>
                  );
                })}
              </Select>
            </FormControl>

            <input
              name="file-dialog"
              type="file"
              onChange={(e: ChangeEvent<HTMLInputElement>) => this.handleChange(e)}
              ref={(ref) => {
                this.uploadDialog = ref;
              }}
              style={{ display: 'none' }}
            />
            <Button
              onClick={(e) => {
                e.preventDefault();
                this.handleChooseFile();
              }}
              variant="outlined"
              color={this.state.file_name ? 'success' : 'error'}
              sx={{ height: '120px', width: '100%' }}
            >
              <FileOpenIcon />
              <div className="file-dialog-upload-button-text">
                {this.state.file_name || 'Choose file'}
              </div>
            </Button>

            <Button
              variant="outlined"
              onClick={(e) => {
                e.preventDefault();
                if (this.state.file_name) {
                  this.upload(1);
                }
              }}
              className="control-button"
            >
              <FileUploadIcon /> Upload
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }
}
