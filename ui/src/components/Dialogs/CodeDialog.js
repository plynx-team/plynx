import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Dialog from './Dialog';
import AceEditor from 'react-ace';
import {CODE_LANGUAGES, CODE_THEMES} from '../../constants';
import 'brace/ext/language_tools';

// Init react-ace

CODE_LANGUAGES.forEach(lang => {
  require(`brace/mode/${lang}`);        // eslint-disable-line global-require
  require(`brace/snippets/${lang}`);    // eslint-disable-line global-require
});

CODE_THEMES.forEach(theme => {
  require(`brace/theme/${theme}`);      // eslint-disable-line global-require
});

// Finish react-ace

export default class CodeDialog extends Component {
  static propTypes = {
    title: PropTypes.string.isRequired,
    readOnly: PropTypes.bool.isRequired,
    value: PropTypes.shape({
      mode: PropTypes.string.isRequired,
      value: PropTypes.string.isRequired,
    }).isRequired,
    onClose: PropTypes.func.isRequired,
    onParameterChanged: PropTypes.func,
  }

  constructor(props) {
    super(props);
    this.state = {
      title: props.title
    };
    this.value = props.value;
  }

  handleChange(value) {
    this.value.value = value;
  }

  handleClose() {
    if (this.props.onParameterChanged) {
      this.props.onParameterChanged(this.value);
    }
    this.props.onClose();
  }

  render() {
    return (
      <Dialog className='CodeDialog'
              onClose={() => {
                this.handleClose();
              }}
              width={900}
              height={500}
              title={this.state.title}
              enableResizing
      >
        <div className="CodeDialogContent">
          <AceEditor
            mode={this.props.value.mode}
            onChange={(value) => this.handleChange(value)}
            editorProps={{$blockScrolling: true}}
            value={this.props.value.value}
            theme="chaos"
            fontSize={14}
            showPrintMargin
            showGutter
            highlightActiveLine
            readOnly={this.props.readOnly}
            width="auto"
            height="468px"
            onLoad={(editor) => {
              this.codeEditor = editor;
              this.codeEditor.focus();
            }}
            setOptions={{
              enableBasicAutocompletion: false,
              enableLiveAutocompletion: false,
              enableSnippets: false,
              showLineNumbers: true,
              tabSize: 4,
            }}
          />
        </div>

      </Dialog>
    );
  }
}
