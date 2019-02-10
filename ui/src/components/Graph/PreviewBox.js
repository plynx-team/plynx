// src/components/About/index.js
import React, { Component } from 'react';
import ParameterItem from './ParameterItem.js'
import OutputItem from './OutputItem.js'
import { PLynxApi } from '../../API.js';
import { API_ENDPOINT } from '../../constants.js';
import './style.css';

export default class PreviewBox extends Component {
  constructor(props) {
    super(props);
    this.state = {
      nodeName: props.nodeName,
      outputName: props.outputName,
      resourceId: props.resourceId,
      fileType: props.fileType,
      content: ""
    };

    if (props.fileType != 'image' && props.fileType != 'pdf') {
      var self = this;
      PLynxApi.endpoints.resource.getOne({ id: props.resourceId})
        .then(function (response) {
          self.setState({content: response.data});
        })
        .catch(function (error) {
          console.error(error);
        });
    }
  }

  handleClose() {
    if (this.props.onCloseAction) {
      this.props.onCloseAction();
    }
  }

  noClick(e) {
    e.stopPropagation();
  }

  render() {
    return (
      <div className="PreviewBoxBackground"
        onClick={() => this.handleClose()}>
        <div className="PreviewBox" onClick={(e) => this.noClick(e)}>
          <div className="PreviewBoxHeader">
            <div className="PreviewBoxTitle">
              Preview: {this.state.nodeName} - {this.state.outputName}
            </div>
            <div className="PreviewBoxClose"
              onClick={() => this.handleClose()}>
              &#215;
            </div>
          </div>
          <div className="PreviewBoxContent">
            {this.state.fileType == 'executable' &&
              <pre>
                {this.state.content}
              </pre>
            }
            {this.state.fileType == 'file' &&
              <pre>
                {this.state.content}
              </pre>
            }
            { this.state.fileType == 'pdf' &&
              <iframe src={API_ENDPOINT + '/resource/' + this.state.resourceId} type="application/pdf" width="100%" height="100%">
                 <p><b>Example fallback content</b>: This browser does not support PDFs. Please download the PDF to view it: <a href="/pdf/sample-3pp.pdf">Download PDF</a>.</p>
              </iframe>
            }
            { this.state.fileType == 'image' &&
              <img src={API_ENDPOINT + '/resource/' + this.state.resourceId} width="100%" />
            }
          </div>
        </div>
      </div>
    );
  }
}
