// src/components/About/index.js
import React, { Component } from 'react';
import Dialog from './Dialog.js'
import AceEditor from 'react-ace';
import 'brace/ext/language_tools';

// Init react-ace

const languages = [
  'python',
];

const themes = [
  'monokai',
];

languages.forEach(lang => {
  require(`brace/mode/${lang}`);
  require(`brace/snippets/${lang}`);
});

themes.forEach(theme => {
  require(`brace/theme/${theme}`);
});

// Finish react-ace

export default class CodeDialog extends Component {
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
              onClose={() => {this.handleClose()}}
              width={900}
              height={500}
              title={this.state.title}
              enableResizing={true}
      >
        <div className="CodeDialogContent">
          <AceEditor
            mode={this.props.value.mode}
            onChange={(value) => this.handleChange(value)}
            editorProps={{$blockScrolling: true}}
            value={this.props.value.value}
            theme="monokai"
            fontSize={14}
            showPrintMargin={true}
            showGutter={true}
            highlightActiveLine={true}
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
