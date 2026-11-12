import React, { Component, ChangeEvent } from 'react';
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

export interface CodeValue {
  mode: string;
  value: string;
}

export interface ValueCodeItemProps {
  name: string;
  readOnly: boolean;
  height?: string;
  showEnumOptions?: boolean;
  value: CodeValue;
  onChange: (event: any) => void;
}

interface ValueCodeItemState {
  readOnly: boolean;
  value: string;
  mode: string;
}

export default class CodeItem extends Component<ValueCodeItemProps, ValueCodeItemState> {
  constructor(props: ValueCodeItemProps) {
    super(props);
    const initialValue = props.value || { value: '', mode: 'python' };
    this.state = {
      readOnly: this.props.readOnly,
      value: initialValue.value || '',
      mode: initialValue.mode || 'python',
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

  handleChange(value: string) {
    if (this.state.readOnly) {
      return;
    }

    this.setState({ value }, () => {
      this.handleCommunacation();
    });
  }

  handleChangeMode(event: ChangeEvent<HTMLSelectElement>) {
    if (this.state.readOnly) {
      return;
    }
    if (event.target.name === 'index') {
      const selectedIndex = parseInt(event.target.value, 10);
      this.setState({ mode: CODE_LANGUAGES[selectedIndex] }, () => {
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
            {CODE_LANGUAGES.map((val, index) => (
              <option value={index} key={index}>
                {val}
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
          height={this.props.height || '300px'}
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
