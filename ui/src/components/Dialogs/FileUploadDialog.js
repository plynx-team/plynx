import React, { Component } from 'react';
import PropTypes from 'prop-types';
// import Dialog from './Dialog';
import { PLynxApi } from '../../API';
import LoadingScreen from '../LoadingScreen';
import Icon from '../Common/Icon';
import { RESPONCE_STATUS } from '../../constants';
import PaperComponent from './DraggableComponent';
import './FileUploadDialog.css';

import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import MenuItem from '@mui/material/MenuItem';
import InputLabel from '@mui/material/InputLabel';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Select from '@mui/material/Select';

import {StyledListItemIcon} from '../Common/MuiComponents';

import FileUploadIcon from '@mui/icons-material/FileUpload';
import FileOpenIcon from '@mui/icons-material/FileOpen';

import { FormControl } from '@mui/material';

const DEFAULT_TITLE = 'File';

export default class FileUploadDialog extends Component {
  static propTypes = {
    onClose: PropTypes.func.isRequired,
    uploadOperation: PropTypes.shape({
      resources: PropTypes.array.isRequired,
      kind: PropTypes.string.isRequired,
    }),
    plugins_info: PropTypes.shape({
      operations_dict: PropTypes.object.isRequired,
      resources_dict: PropTypes.object.isRequired,
    }).isRequired,
    onUpload: PropTypes.func,
    doNotSave: PropTypes.bool,
  };

  constructor(props) {
    super(props);
    this.state = {
      title: DEFAULT_TITLE,
      description: '',
      file_type: this.props.plugins_info.operations_dict[props.uploadOperation.kind].resources[0].kind,
      file_path: null,
      file_name: null,
      uploadProgress: 10,
      loading: false
    };
  }

  handleChange(event) {
    const name = event.target.name;
    console.log(name, event.target.value);

    this.setState({
      [name]: event.target.value
    });

    if (name === 'file-dialog') {
      console.log(event.target.files[0]);
      this.file = event.target.files[0];
      if (this.file && this.file.name) {
        const extension = this.file.name.split('.').pop().toUpperCase();

        for (const resource of this.props.uploadOperation.resources) {
          if (resource.extensions.map(st => st.toUpperCase()).indexOf(extension) !== -1) {
            this.setState({file_type: resource.kind});
          }
        }
      }

      this.setState({
        file_path: this.file,
        file_name: this.file ? this.file.name : null,
        title: this.file && this.state.title === DEFAULT_TITLE ? this.file.name : this.state.title
      });
    }
  }

  handleChooseFile() {
    this.uploadDialog.click();
  }

  upload(retryCount) {
    const self = this;
    const formData = new FormData();
    formData.append('data', this.file);
    formData.append('title', self.state.title);
    formData.append('description', self.state.description);
    formData.append('file_type', self.state.file_type);
    formData.append('node_kind', self.props.uploadOperation.kind);
    formData.append('do_not_save', !!self.props.doNotSave);
    console.log(self.props.uploadOperation.kind);

    const config = {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress(progressEvent) {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        self.setState({
          uploadProgress: percentCompleted
        });
      }
    };

    self.setState({loading: true});
    PLynxApi.endpoints.upload_file.upload(formData, config)
    .then((response) => {
      const data = response.data;
      console.log(data);

      if (data.status === RESPONCE_STATUS.SUCCESS) {
        self.props.onClose();
        self.setState({loading: false});
      }
      if (this.props.onUpload) {
        this.props.onUpload(data.node);
      }
    }).catch((error) => {
      console.error('error', error);

      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
          } else if (retryCount > 0) {
            self.upload(retryCount - 1);
            return;
          }
        });
      } else {
        self.props.showAlert('Failed to upload file. Did you choose the right file type?', 'failed');
      }
      self.setState({loading: false});
    });
  }

  render() {
    return (
      <Dialog className="mui-dialog"
              open
              onClose={() => {
                this.props.onClose();
              }}
              aria-labelledby="draggable-dialog-title"
              aria-describedby="scroll-dialog-description"
              fullWidth
              PaperComponent={PaperComponent}
      >
      <DialogTitle className='mui-dialog-title'>Upload a File</DialogTitle>
      {this.state.loading &&
        <div className='LoadHolder'>
          <LoadingScreen />
        </div>
      }
      <DialogContent
        className="mui-dialog-content"
        >
          <div
            className='mui-dialog-file-upload'
          >
            <TextField
              id="standard-basic"
              label="Title"
              variant="outlined"
              value={this.state.title}
              name="title"
              onChange={(e) => this.handleChange(e)}
              error={this.state.title === ''}
              className='mui-text-field'
            />

            <TextField
              id="standard-basic"
              label="Description"
              variant="outlined"
              value={this.state.description}
              name="description"
              onChange={(e) => this.handleChange(e)}
              className='mui-text-field'
            />

            <FormControl fullWidth>
              <InputLabel id="demo-simple-select-label">File type</InputLabel>
              <Select
                labelId="demo-simple-select-label"
                id="demo-simple-select"
                label="File type"

                name='file_type'
                value={this.state.file_type}
                onChange={(e) => this.handleChange(e)}
              >
                {
                  Object.values(this.props.uploadOperation.resources).map((description) => <MenuItem
                    value={description.kind}
                    key={description.kind}
                    >
                      <StyledListItemIcon>
                        <Icon
                          type_descriptor={this.props.plugins_info.resources_dict[description.kind]}
                          width={"20"}
                          height={"20"}
                        />
                      </StyledListItemIcon>
                      {description.title}
                  </MenuItem>
                  )
                }

              </Select>
            </FormControl>

            {/* Upload dialgo */}
            <input
              name="file-dialog"
              type="file"
              onChange={(e) => this.handleChange(e)}
              ref={(ref) => this.uploadDialog = ref} style={{ display: 'none' }}
            />
            <Button
              onClick={(e) => {
                e.preventDefault();
                this.handleChooseFile();
              }}
              variant='outlined'
              color={this.state.file_name ? 'success' : 'error'}
              sx={{height: "120px", width: "100%"}}
            >
              <FileOpenIcon/>
              <div className="file-dialog-upload-button-text">{this.state.file_name || 'Choose file'}</div>
            </Button>

            <Button
              variant='outlined'
              onClick={(e) => {
                e.preventDefault();
                if (this.state.file_name) {
                  this.upload(1);
                }
              }}
               className="control-button">
              <FileUploadIcon/> Upload
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }
}
