// src/components/About/index.js
import React, { Component } from 'react';
import ReactDOM from 'react-dom';
import AlertContainer from 'react-alert-es6';
import { PlynxApi } from '../../API.js';
import FileList from './FileList.js'
import ReactPaginate from 'react-paginate';
import LoadingScreen from '../LoadingScreen.js'
import FileDialog from '../Dialogs/FileDialog.js'
import FileUploadDialog from '../Dialogs/FileUploadDialog.js'
import PreviewDialog from '../Dialogs/PreviewDialog.js'
import { ACTION, ALERT_OPTIONS, RESPONCE_STATUS } from '../../constants.js';
import SearchBar from '../Common/SearchBar.js';
import './style.css';
import '../Common/ListPage.css';
import '../controls.css';


export default class FileListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Files List - Plynx";
    this.state = {
      nodes: [],
      loading: true,
      pageCount: 0,
      search: "",
      fileObj: null,
      uploadFile: false,
      previewData: null,
    };
    this.perPage = 20;

    this.loadFiles();
  }

  showAlert(message, type) {
    this.msg.show(message, {
      time: 5000,
      type: 'error',
      icon: <img src={"/alerts/" + type +".svg"} width="32" height="32" alt={type}/>
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

    var self = this;
    var loading = true;
    var sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    if (this.mounted) {
      self.setState({
        loading: true,
      });
    }

    var handleResponse = function (response) {
      let data = response.data;
      console.log(data.nodes);
      self.setState(
        {
          nodes: data.nodes,
          pageCount: Math.ceil(data.total_count / self.perPage)
        });
      loading = false;
      ReactDOM.findDOMNode(self.fileList).scrollTop = 0;
    };

    var handleError = function (error) {
      if (error.response.status === 401) {
        PlynxApi.getAccessToken()
        .then(function (isSuccessfull) {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.props.history.push("/login/");
          } else {
            self.showAlert('Updated access token', 'success');
          }
        });
      }
    };

    while (loading) {
      await PlynxApi.endpoints.nodes.getAll( {
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

    // Stop loading
    self.setState({
      loading: false,
    });
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  handlePageClick = (data) => {
    let selected = data.selected;
    let offset = Math.ceil(selected * this.perPage);
    console.log(selected, offset);

    this.setState({offset: offset}, () => {
      this.loadNodes();
    });
  };

  handlePageClick = (data) => {
    let selected = data.selected;
    let offset = Math.ceil(selected * this.perPage);
    console.log(selected, offset);

    this.setState({offset: offset}, () => {
      this.loadFiles();
    });
    ReactDOM.findDOMNode(this.fileList).scrollTop = 0
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
    /*action might be in {'save', 'validate', 'approve', 'deprecate'}*/
    var self = this;
    self.setState({loading: true});
    PlynxApi.endpoints.nodes
    .create({
      body: {
        node: file,
        action: action
      }
    })
    .then(function (response) {
      var data = response.data;
      console.log(data);
      self.setState({loading: false});
      if (data.status === RESPONCE_STATUS.SUCCESS) {
        self.loadFiles();
        self.showAlert("Saved", 'success');
      } else if (data.status === RESPONCE_STATUS.VALIDATION_FAILED) {
        console.warn(data.message);
        // TODO smarter traverse
        var validationErrors = data.validation_error.children;
        for (var i = 0; i < validationErrors.length; ++i) {
          var validationError = validationErrors[i];
          self.showAlert(validationError.validation_code + ': ' + validationError.object_id, 'warning');
        }

        self.showAlert(data.message, 'failed');
      } else {
        console.warn(data.message);
        self.showAlert(data.message, 'failed');
      }
    })
    .catch(function (error) {
      if (error.response.status === 401) {
        PlynxApi.getAccessToken()
        .then(function (isSuccessfull) {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.showAlert('Failed to authenticate', 'failed');
          } else {
            if (retryCount > 0) {
              self.postFile(file, action, retryCount - 1);
              return;
            }
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
    })
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
      <div className='ListPage'>
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
                  ref={(child) => { this.fileList = child; }}
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
      </div>
    );
  }
}
