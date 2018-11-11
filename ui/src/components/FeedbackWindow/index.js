// src/components/NotFound/index.js
import React, { Component } from 'react';
import { PlynxApi } from '../../API.js';
import { RESPONCE_STATUS } from '../../constants.js';
import cookie from 'react-cookies'

import './style.css';

export default class FeedbackWindow extends Component {
  constructor(props) {
    super(props);
    this.state = {
      name: "",
      email: "",
      message: ""
    };
  }

  handleFieldChange(fieldName, event) {
    this.setState({[fieldName]: event.target.value});
  }

  handleSend(e) {
    if (this.state.message) {
      this.postFeedback(this.state.name, this.state.email, this.state.message);
      this.handleClose(e)
    }
  }

  handleClose(e) {
    e.preventDefault();
    this.props.onClose();
  }

  postFeedback(name, email, message) {
    /*action might be in {'save', 'validate', 'approve', 'deprecate'}*/
    var self = this;
    self.setState({loading: true});
    PlynxApi.endpoints.feedback
    .create({
      body: {
        name: name,
        email: email,
        message: message,
        username: cookie.load('username'),
        url: document.URL
      }
    })
    .then(function (response) {
      var data = response.data;
      if (data.status === RESPONCE_STATUS.SUCCESS) {
        self.handleClose()
      } else if (data.status === RESPONCE_STATUS.VALIDATION_FAILED) {
        console.warn(data.message);
      } else {
        console.warn(data.message);
      }
    })
    .catch(function (error) {
      console.error(error);
    });
  }

  render() {
    var self = this;
    return (
      <div className='FeedbackWindow'
           onClick={(e) => this.handleClose(e)}>
        <div className='FeedbackWindowBlock'
             onClick={(e) => e.stopPropagation()}>
          <h1>
            Feedback
          </h1>
          <p>{"Thank you for trying PLynx! We appreciate any feedback. Please enter your email if you would like to receive a response from us."}</p>
          <div className="content">

            <div className="row">
              <div className="title">
                {"Name:"}
              </div>
              <div className="value">
                <input value={this.state.name}
                       className="name"
                       onChange={(e) => self.handleFieldChange("name", e)}
                       />
              </div>
            </div>

            <div className="row">
              <div className="title">
                {"E-mail:"}
              </div>
              <div className="value">
              <input value={this.state.email}
                     className="email"
                     onChange={(e) => self.handleFieldChange("email", e)}
                     />
              </div>
            </div>

            <div className="row">
              <div className="title">
                {"Text:"}
              </div>
              <div className="value">
                <textarea value={this.state.message}
                          className="message"
                          rows="8"
                          onChange={(e) => self.handleFieldChange("message", e)}
                          />
              </div>
            </div>

          </div>
          <a
            className={'close-button'}
            onClick={(e) => this.handleClose(e)}
            href=""
            >
            &#215;
          </a>
          <div className="SendButton" onClick={(e) => this.handleSend(e)}>
            Send
          </div>
        </div>
      </div>
    );
  }
}
