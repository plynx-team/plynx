// src/components/About/index.js
import React, { Component } from 'react';
import ReactDOM from 'react-dom';
import AlertContainer from 'react-alert-es6';
import cookie from 'react-cookies';
import { PLynxApi } from '../../API';
import FileList from './FileList';
import ReactPaginate from 'react-paginate';
import LoadingScreen from '../LoadingScreen';
import FileDialog from '../Dialogs/FileDialog';
import FileUploadDialog from '../Dialogs/FileUploadDialog';
import PreviewDialog from '../Dialogs/PreviewDialog';
import { ACTION, ALERT_OPTIONS, RESPONCE_STATUS, KEY_MAP } from '../../constants';
import SearchBar from '../Common/SearchBar';
import {HotKeys} from 'react-hotkeys';
import './style.css';
import '../Common/ListPage.css';
import '../controls.css';


export default class FileListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Files List - PLynx";
    const username = cookie.load('username');
    this.state = {
      nodes: [],
      loading: true,
      pageCount: 0,
      search: username ? 'author:' + username + ' ' : '',
      fileObj: null,
      uploadFile: false,
      previewData: null,
    };
    this.perPage = 20;

    this.loadFiles();
  }

  keyHandlers = {
    escPressed: () => {
      this.handleCloseDialog();
    },
  }

  showAlert(message, type) {
    this.msg.show(message, {
      time: 5000,
      type: 'error',
      icon: <img src={"/alerts/" + type + ".svg"} width="32" height="32" alt={type}/>
    });
  }

  componentDidMount() {
    this.mounted = true;
  }

  componentWillUnmount() {
    this.mounted = false;
  }

  async loadFiles() {
    // Loading

    const self = this;
    let loading = true;
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    if (this.mounted) {
      self.setState({
        loading: true,
      });
    }

    const handleResponse = (response) => {
      const data = response.data;
      console.log(data.nodes);
      self.setState(
        {
          nodes: data.nodes,
          pageCount: Math.ceil(data.total_count / self.perPage)
        });
      loading = false;
      ReactDOM.findDOMNode(self.fileList).scrollTop = 0;
    };

    const handleError = (error) => {
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.props.history.push("/login/");
          } else {
            self.showAlert('Updated access token', 'success');
          }
        });
      }
    };

    /* eslint-disable no-await-in-loop */
    /* eslint-disable no-unmodified-loop-condition */
    while (loading) {
      await PLynxApi.endpoints.nodes.getAll({
        query: {
          offset: self.state.offset,
          per_page: self.perPage,
          base_node_names: ['file'],
          search: self.state.search,
        }
      })
      .then(handleResponse)
      .catch(handleError);
      if (loading) {
        await self.sleep(sleepPeriod);
        sleepPeriod = Math.min(sleepPeriod + sleepStep, sleepMaxPeriod);
      }
    }
    /* eslint-enable no-unmodified-loop-condition */
    /* eslint-enable no-await-in-loop */

    // Stop loading
    self.setState({
      loading: false,
    });
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  handlePageClick = (data) => {
    const selected = data.selected;
    const offset = Math.ceil(selected * this.perPage);
    console.log(selected, offset);

    this.setState({offset: offset}, () => {
      this.loadNodes();
    });
  };

  handlePageClick = (data) => {
    const selected = data.selected;
    const offset = Math.ceil(selected * this.perPage);
    console.log(selected, offset);

    this.setState({offset: offset}, () => {
      this.loadFiles();
    });
    ReactDOM.findDOMNode(this.fileList).scrollTop = 0;
  };

  handleFileClick(fileObj) {
    this.setState({
      fileObj: fileObj,
      uploadFile: false
    });
  }

  handleCloseDialog() {
    this.setState({
      fileObj: null,
      uploadFile: false
    });
  }

  postFile(file, action, retryCount) {
    /* action might be in {'save', 'validate', 'approve', 'deprecate'}*/
    const self = this;
    self.setState({loading: true});
    PLynxApi.endpoints.nodes
    .create({
      body: {
        node: file,
        action: action
      }
    })
    .then((response) => {
      const data = response.data;
      console.log(data);
      self.setState({loading: false});
      if (data.status === RESPONCE_STATUS.SUCCESS) {
        self.loadFiles();
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

  handleDeprecate(fileObj) {
    this.postFile(fileObj, ACTION.DEPRECATE, 1);
  }

  handleNewFileClick(e) {
    e.stopPropagation();
    e.preventDefault();

    this.setState({
      fileObj: null,
      uploadFile: true
    });
  }

  handleSearchUpdate(search) {
    this.setState({
      offset: 0,
      search: search,
    }, () => {
      this.loadFiles();
    });
  }

  handlePreview(data) {
    this.setState({previewData: data});
  }

  handleClosePreview() {
    this.setState({previewData: null});
  }

  render() {
    return (
      <HotKeys className='ListPage'
               handlers={this.keyHandlers} keyMap={KEY_MAP}
      >
        {this.state.loading &&
          <LoadingScreen />
        }
        <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
        <div className="menu">
          <a className="menu-button"
             href={null}
             onClick={(e) => this.handleNewFileClick(e)}
             >
            {"Create new File"}
          </a>
        </div>
        <div className="search">
          <SearchBar
              onSearchUpdate={(search) => this.handleSearchUpdate(search)}
              search={this.state.search}
          />
        </div>
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
        {this.state.uploadFile &&
          <FileUploadDialog
            onClose={() => this.handleCloseDialog()}
            onPostFile={(file) => this.postFile(file, ACTION.SAVE, 1)}
          />
        }
        <FileList files={this.state.nodes}
                  ref={(child) => {
                    this.fileList = child;
                  }}
                  onClick={(fileObj) => this.handleFileClick(fileObj)}
        />
        <ReactPaginate previousLabel={"Previous"}
                       nextLabel={"Next"}
                       breakLabel={<a>...</a>}
                       breakClassName={"break-me"}
                       pageCount={this.state.pageCount}
                       marginPagesDisplayed={2}
                       pageRangeDisplayed={5}
                       onPageChange={this.handlePageClick}
                       containerClassName={"pagination"}
                       subContainerClassName={"pages pagination"}
                       activeClassName={"active"} />
      </HotKeys>
    );
  }
}
