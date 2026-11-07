import React, { Component } from 'react';
import PropTypes from 'prop-types';
import AceEditor from 'react-ace';
import { CODE_LANGUAGES } from '../../constants';
import 'ace-builds/src-noconflict/mode-python';
import 'ace-builds/src-noconflict/mode-sh';
import 'ace-builds/src-noconflict/snippets/python';
import 'ace-builds/src-noconflict/snippets/sh';
import 'ace-builds/src-noconflict/theme-chaos';
import 'ace-builds/src-noconflict/ext-language_tools';
import 'ace-builds/src-noconflict/ext-searchbox';

import './ValueCodeItem.css';

export default class CodeItem extends Component {
  static propTypes = {
    name: PropTypes.string.isRequired,
    readOnly: PropTypes.bool.isRequired,
    height: PropTypes.string.isRequired,
    showEnumOptions: PropTypes.bool.isRequired,
    value: PropTypes.shape({
      mode: PropTypes.string.isRequired,
      value: PropTypes.string.isRequired,
    }).isRequired,
    onChange: PropTypes.func.isRequired,
  };

  constructor(props) {
    super(props);
    this.state = {
      readOnly: this.props.readOnly,
      value: this.props.value.value,
      mode: this.props.value.mode,
    };

    this.handleChange = this.handleChange.bind(this);
  }

  handleCommunacation() {
    this.props.onChange({
      target: {
        name: this.props.name,
        value: {
          mode: this.state.mode,
          value: this.state.value,
        },
        type: 'code',
      },
    });
  }

  handleChange(value) {
    if (this.state.readOnly) {
      return;
    }

    this.setState({ value: value }, () => {
      this.handleCommunacation();
    });
  }

  handleChangeMode(event) {
    if (this.state.readOnly) {
      return;
    }
    if (event.target.name === 'index') {
      this.setState({ mode: CODE_LANGUAGES[event.target.value] }, () => {
        this.handleCommunacation();
      });
    }
  }

  render() {
    return (
      <div
        className="CodeItem"
        onMouseDown={(e) => {
          e.stopPropagation();
        }}
      >
        <div className="code-mode">
          <select
            className="code-mode-select"
            name="index"
            value={CODE_LANGUAGES.indexOf(this.state.mode)}
            onChange={(e) => {
              this.handleChangeMode(e);
            }}
            disabled={this.state.readOnly}
          >
            {CODE_LANGUAGES.map((value, index) => (
              <option value={index} key={index}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <AceEditor
          mode={this.state.mode}
          onChange={this.handleChange}
          editorProps={{ $blockScrolling: true }}
          value={this.state.value}
          theme="chaos"
          fontSize={14}
          showPrintMargin
          showGutter
          highlightActiveLine
          readOnly={this.state.readOnly}
          width="auto"
          height={this.props.height}
          setOptions={{
            useWorker: false,
            enableBasicAutocompletion: false,
            enableLiveAutocompletion: false,
            enableSnippets: false,
            showLineNumbers: true,
            tabSize: 4,
          }}
        />
      </div>
    );
  }
}
