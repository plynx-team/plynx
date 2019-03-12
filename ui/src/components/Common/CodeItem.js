// src/components/About/index.js
import React, { Component } from 'react';
import AceEditor from 'react-ace';
import {CODE_LANGUAGES, CODE_THEMES} from '../../constants'
import 'brace/ext/language_tools';
import 'brace/ext/searchbox';

import './CodeItem.css';

// Init react-ace

CODE_LANGUAGES.forEach(lang => {
  require(`brace/mode/${lang}`);
  require(`brace/snippets/${lang}`);
});

CODE_THEMES.forEach(theme => {
  require(`brace/theme/${theme}`);
});

// Finish react-ace

export default class EnumItem extends Component {
  constructor(props) {
    super(props);
    this.state = {
      readOnly: this.props.readOnly || !this.props.showEnumOptions,
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
          type: 'code'
        }
    });
  }

  handleChange(value) {
    if (this.state.readOnly) {
      return;
    }

    this.setState({value: value}, () => {
      this.handleCommunacation();
    });
  }

  handleChangeMode(event) {
    if (this.state.readOnly) {
      return;
    }
    if (event.target.name === 'index') {
      this.setState({mode: CODE_LANGUAGES[event.target.value]}, () => {
        this.handleCommunacation();
      });
    }
  }

  render() {
    return (
      <div className='CodeItem'
           onMouseDown={(e) => {e.stopPropagation()}}
      >
        <div className='code-mode'>
          <select className='code-mode-select'
              type='text'
              name='index'
              value={CODE_LANGUAGES.indexOf(this.state.mode)}
              onChange={(e) => {this.handleChangeMode(e)}}
              readOnly={this.state.readOnly}
            >
              {
                CODE_LANGUAGES.map((value, index) =>
                  <option
                    value={index}
                    key={index}
                    >
                    {value}
                    </option>
                )
              }
          </select>
        </div>
        <AceEditor
          mode={this.state.mode}
          onChange={this.handleChange}
          editorProps={{$blockScrolling: true}}
          value={this.state.value}
          theme="chaos"
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
