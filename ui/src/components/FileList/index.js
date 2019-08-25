import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import BaseList from '../BaseList';
import {ResourceConsumer} from '../../contexts';
import {HotKeys} from 'react-hotkeys';
import Icon from '../Common/Icon';
import FileDialog from '../Dialogs/FileDialog';
import FileUploadDialog from '../Dialogs/FileUploadDialog';
import PreviewDialog from '../Dialogs/PreviewDialog';
import { listTextElement } from '../Common/listElements';
import { ACTION, RESPONCE_STATUS, KEY_MAP } from '../../constants';
import '../Common/ListPage.css';
import '../controls.css';
import './items.css';


export default class ListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Files - PLynx";
    this.state = {
      fileObj: null,
      uploadFile: false,
      previewData: null,
    };
    this.perPage = 20;
  }

  keyHandlers = {
    escPressed: () => {
      this.handleCloseDialog();
    },
  }

  renderItem(node) {
    const file_type = node.outputs[0].file_type;
    return (
        <div
          className='list-item file-list-item'
          onClick={() => this.handleFileClick(node)}
          key={node._id}
        >

          <div className='ItemHeader'>
            <div className='TitleDescription'>
              <div className='Title'>
                {node.title}
              </div>
              <div className='Description'>
                &ldquo;{node.description}&rdquo;
              </div>
            </div>
            <div className={node.starred ? 'star-visible' : 'star-hidden'}>
              <img src="/icons/star.svg" alt="star" />
            </div>
          </div>

          <div className={'Type'}>
            <ResourceConsumer className={'Type'}>
            { resources_dict => <div className='Widget'>
                <Icon
                  type_descriptor={resources_dict[file_type]}
                  width={"20"}
                  height={"20"}
                />

                {resources_dict[file_type].alias}
              </div>
            }
            </ResourceConsumer>
          </div>
          { listTextElement('Status ' + node.node_status, node.node_status) }
          { listTextElement('Id', node._id) }
          { listTextElement('Author', node._user[0].username) }
          { listTextElement('Created', node.insertion_date) }
        </div>
    );
  }

  postFile(file, action, retryCount) {
    /* action might be in {'save', 'validate', 'approve', 'deprecate'}*/
    const self = this;
    self.setState({loading: true});
    PLynxApi.endpoints.nodes
    .create({
      node: file,
      action: action
    })
    .then((response) => {
      const data = response.data;
      console.log(data);
      self.setState({loading: false});
      if (data.status === RESPONCE_STATUS.SUCCESS) {
        window.location.reload();
        self.showAlert("Saved", 'success');
      } else if (data.status === RESPONCE_STATUS.VALIDATION_FAILED) {
        console.warn(data.message);
        // TODO smarter traverse
        const validationErrors = data.validation_error.children;
        for (let i = 0; i < validationErrors.length; ++i) {
          const validationError = validationErrors[i];
          self.showAlert(validationError.validation_code + ': ' + validationError.object_id, 'warning');
        }

        self.showAlert(data.message, 'failed');
      } else {
        console.warn(data.message);
        self.showAlert(data.message, 'failed');
      }
    })
    .catch((error) => {
      console.log('!!!@#@!#!', error);
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.showAlert('Failed to authenticate', 'failed');
          } else if (retryCount > 0) {
            self.postFile(file, action, retryCount - 1);
            return;
          }
        });
      } else {
        self.showAlert('Failed to save the file', 'failed');
      }
      self.setState({loading: false});
    });
  }

  handleNewFileClick(e) {
    e.stopPropagation();
    e.preventDefault();

    this.setState({
      fileObj: null,
      uploadFile: true
    });
  }

  handleDeprecate(fileObj) {
    this.postFile(fileObj, ACTION.DEPRECATE, 1);
  }

  handlePreview(data) {
    this.setState({previewData: data});
  }

  handleClosePreview() {
    this.setState({previewData: null});
  }

  handleFileClick(fileObj) {
    this.setState({
      fileObj: fileObj,
      uploadFile: false
    });
  }

  handleCloseDialog() {
    this.setState({
      fileObj: null,
      uploadFile: false,
      previewData: null,
    });
  }


  render() {
    const header = [
       {title: "Header", tag: ""},
       {title: "Type", tag: "Type"},
       {title: "Status", tag: "Status"},
       {title: "Id", tag: "Id"},
       {title: "Author", tag: "Author"},
       {title: "Created", tag: "Created"},
    ];
    return (
        <HotKeys className='ListPage'
                 handlers={this.keyHandlers} keyMap={KEY_MAP}
        >
            <BaseList
                menu={() => <div className="menu-button"
                       onClick={(e) => this.handleNewFileClick(e)}
                       >
                      {"Create new File"}
                    </div>
                    }
                tag="file-list-item"
                endpoint={PLynxApi.endpoints.search_nodes}
                extraSearch={{base_node_names: ['file']}}
                header={header}
                renderItem={(node) => this.renderItem(node)}
            >
                {this.state.uploadFile &&
                  <FileUploadDialog
                    onClose={() => this.handleCloseDialog()}
                    onPostFile={(file) => this.postFile(file, ACTION.SAVE, 1)}
                  />
                }
                {this.state.fileObj &&
                  <FileDialog
                    onClose={() => this.handleCloseDialog()}
                    onDeprecate={(fileObj) => this.handleDeprecate(fileObj)}
                    fileObj={this.state.fileObj}
                    hideDeprecate={this.state.fileObj._readonly}
                    onPreview={(previewData) => this.handlePreview(previewData)}
                    />
                }
                {
                  this.state.previewData &&
                  <PreviewDialog className="PreviewDialog"
                    title={this.state.previewData.title}
                    file_type={this.state.previewData.file_type}
                    resource_id={this.state.previewData.resource_id}
                    download_name={this.state.previewData.download_name}
                    onClose={() => this.handleClosePreview()}
                  />
                }
            </BaseList>
        </HotKeys>
    );
  }
}
