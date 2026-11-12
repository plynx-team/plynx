import React, { Component } from 'react';
import AceEditor from 'react-ace';
import Paper from '@mui/material/Paper';
import Box from '@mui/material/Box';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Typography from '@mui/material/Typography';
import CodeIcon from '@mui/icons-material/Code';
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

  handleChangeMode(event: SelectChangeEvent<number>) {
    if (this.state.readOnly) {
      return;
    }
    const selectedIndex = Number(event.target.value);
    const newMode = CODE_LANGUAGES[selectedIndex] || 'python';
    this.setState({ mode: newMode }, () => {
      this.handleCommunacation();
    });
  }

  render() {
    const languageIndex = Math.max(0, CODE_LANGUAGES.indexOf(this.state.mode));

    return (
      <Paper
        className="CodeItem"
        elevation={2}
        sx={{
          backgroundColor: '#1b1b1b',
          border: '1px solid #333',
          borderRadius: '4px',
          overflow: 'hidden',
        }}
        onMouseDown={(e) => {
          e.stopPropagation();
        }}
      >
        <Box
          className="code-mode"
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '4px 8px',
            backgroundColor: '#262626',
            borderBottom: '1px solid #333',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CodeIcon fontSize="small" sx={{ color: '#888' }} />
            <Typography variant="caption" sx={{ color: '#aaa', fontWeight: 600 }}>
              CODE EDITOR
            </Typography>
          </Box>
          <FormControl size="small" variant="outlined" sx={{ minWidth: 110 }}>
            <Select
              className="code-mode-select"
              value={languageIndex}
              onChange={(e) => this.handleChangeMode(e)}
              disabled={this.state.readOnly}
              sx={{
                height: 26,
                fontSize: '0.8rem',
                color: '#fff',
                backgroundColor: '#333',
                '& .MuiSelect-select': {
                  paddingY: 0,
                  paddingLeft: 1,
                },
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#444',
                },
              }}
            >
              {CODE_LANGUAGES.map((val, index) => (
                <MenuItem value={index} key={val} sx={{ fontSize: '0.85rem' }}>
                  {val}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
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
          width="100%"
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
      </Paper>
    );
  }
}
