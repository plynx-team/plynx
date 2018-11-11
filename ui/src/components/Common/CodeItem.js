// src/components/About/index.js
import React, { Component } from 'react';
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

export default class EnumItem extends Component {
  constructor(props) {
    super(props);
    this.state = {
      readOnly: this.props.readOnly,
      value: this.props.value.value,
      mode: this.props.value.mode,
    };

    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(value) {
    if (this.state.readOnly) {
      return;
    }

    this.setState({value: value}, () => {
      this.props.onChange({
          target: {
            name: this.props.name,
            value: {
              mode: this.state.mode,
              value: this.state.value,
            },
            type: 'code'
          }
      });
    });
  }

  render() {
    return (
      <div className='EnumItem'>
        <AceEditor
          mode="python"
          onChange={this.handleChange}
          editorProps={{$blockScrolling: true}}
          value={this.state.value}
          theme="monokai"
          fontSize={14}
          showPrintMargin={true}
          showGutter={true}
          highlightActiveLine={true}
          readOnly={this.state.readOnly}
          width="auto"
          height={this.props.height}
          setOptions={{
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
