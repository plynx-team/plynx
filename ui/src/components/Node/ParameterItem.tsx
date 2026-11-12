import React, { Component } from 'react';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import { PARAMETER_TYPES } from '../../constants';
import renderValueElement from '../Common/renderValueElement';
import './ParameterItem.css';

export function getDefaultParameterValue(parameter_type: string): any {
  switch (parameter_type) {
    case 'str':
      return '';
    case 'int':
      return '0';
    case 'float':
      return '0.0';
    case 'bool':
      return false;
    case 'text':
      return '';
    case 'enum':
      return { index: 0, values: ['enum'] };
    case 'list_str':
      return [];
    case 'list_int':
      return [];
    case 'code':
      return { value: '', mode: 'python' };
    default:
      throw new Error(`Unknown type \`${parameter_type}\``);
  }
}

export interface NodeParameterItemProps {
  name: string;
  parameter_type: string;
  value: any;
  widget?: string | null;
  readOnly?: boolean;
  mutable_type?: boolean;
  publicable?: boolean;
  removable?: boolean;
  onChanged?: (index: number, name: string, value: any) => void;
  index: number;
  onRemove?: (index: number) => void;
  _key?: string;
}

interface NodeParameterItemState {
  name: string;
  parameter_type: string;
  value: any;
  widget?: string | null;
  readOnly?: boolean;
  mutable_type?: boolean;
  publicable?: boolean;
  removable?: boolean;
  remove_hover?: boolean;
}

export default class ParameterItem extends Component<NodeParameterItemProps, NodeParameterItemState> {
  constructor(props: NodeParameterItemProps) {
    super(props);
    this.state = {
      name: this.props.name,
      parameter_type: this.props.parameter_type,
      value: this.props.value,
      widget: this.props.widget,
      readOnly: this.props.readOnly,
      mutable_type: this.props.mutable_type,
      publicable: this.props.publicable,
      removable: this.props.removable,
      remove_hover: false,
    };

    this.handleChange = this.handleChange.bind(this);
  }

  componentDidUpdate(prevProps: NodeParameterItemProps) {
    if (
      prevProps.name !== this.props.name ||
      prevProps.widget !== this.props.widget ||
      prevProps.parameter_type !== this.props.parameter_type ||
      prevProps.value !== this.props.value ||
      prevProps.readOnly !== this.props.readOnly
    ) {
      this.setState({
        name: this.props.name,
        parameter_type: this.props.parameter_type,
        value: this.props.value,
        widget: this.props.widget,
        readOnly: this.props.readOnly,
      });
    }
  }

  handleChange(event: any) {
    if (this.state.readOnly) {
      return;
    }
    const name = event.target.name;
    let value = event.target.value;
    if (name === 'widget_checkbox') {
      value = event.target.checked ? this.state.name : null;
    }
    if (name === 'parameter_type') {
      this.setState({
        value: getDefaultParameterValue(value),
      });
      if (this.props.onChanged) {
        this.props.onChanged(this.props.index, 'value', getDefaultParameterValue(value));
      }
    }
    if (name === 'widget_alias') {
      this.setState({ widget: value });
      if (this.props.onChanged) {
        this.props.onChanged(this.props.index, 'widget', value);
      }
      return;
    }
    this.setState({ [name]: value } as any);
    if (this.props.onChanged) {
      this.props.onChanged(this.props.index, name, value);
    }
  }

  handleTypeChange(newType: string) {
    if (this.state.readOnly && this.state.mutable_type) {
      return;
    }
    const defaultValue = getDefaultParameterValue(newType);
    this.setState({
      parameter_type: newType,
      value: defaultValue,
    });
    if (this.props.onChanged) {
      this.props.onChanged(this.props.index, 'parameter_type', newType);
      this.props.onChanged(this.props.index, 'value', defaultValue);
    }
  }

  handleRemoveItem() {
    if (this.props.onRemove) {
      this.props.onRemove(this.props.index);
    }
  }

  render() {
    return (
      <div className={`ParameterListItem parameter-${this.state.name.replace(' ', '_')}`} style={{ position: 'relative' }}>
        <div className="ParameterFirstItem">
          <div className="ParameterRow">
            <div className="ParameterCellTitle">Name:</div>
            <div className="ParameterCellValue">
              <input
                className="ParameterValue"
                type="text"
                name="name"
                value={this.state.name}
                onChange={this.handleChange}
                readOnly={this.state.readOnly}
              />
            </div>
          </div>

          <div className="ParameterRow">
            <div className="ParameterCellTitle">Type:</div>
            <div className="ParameterCellValue">
              <FormControl size="small" fullWidth>
                <Select
                  className="ParameterValue"
                  value={this.state.parameter_type}
                  onChange={(e: SelectChangeEvent) => this.handleTypeChange(e.target.value)}
                  disabled={Boolean(this.state.readOnly && this.state.mutable_type)}
                  sx={{
                    height: 24,
                    fontSize: '11pt',
                    color: '#fff',
                    backgroundColor: '#262626',
                    '& .MuiSelect-select': {
                      paddingY: '1px',
                      paddingLeft: '6px',
                    },
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#444',
                    },
                  }}
                >
                  {PARAMETER_TYPES.map((description) => (
                    <MenuItem value={description.type} key={description.type} sx={{ fontSize: '0.85rem' }}>
                      {description.alias}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </div>
          </div>

          {this.state.publicable && (
            <div className="ParameterRow">
              <div className="ParameterCellTitle">Widget:</div>
              <div className="ParameterCellValue" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <FormControlLabel
                  control={
                    <Checkbox
                      size="small"
                      name="widget_checkbox"
                      onChange={this.handleChange}
                      checked={this.state.widget !== null && this.state.widget !== undefined}
                      disabled={this.state.readOnly}
                      sx={{ color: '#888', '&.Mui-checked': { color: '#2196F3' } }}
                    />
                  }
                  label="Public"
                  sx={{ margin: 0, '& .MuiFormControlLabel-label': { fontSize: '0.85rem', color: '#eee' } }}
                />
                {this.state.widget !== null && this.state.widget !== undefined && (
                  <input
                    className="ParameterValue"
                    type="text"
                    name="widget_alias"
                    value={this.state.widget}
                    onChange={this.handleChange}
                    readOnly={this.state.readOnly}
                  />
                )}
              </div>
            </div>
          )}
        </div>
        <div className="ParameterSecondItem">
          {!this.state.readOnly && this.state.removable && (
            <IconButton
              size="small"
              className="Remove"
              onClick={() => this.handleRemoveItem()}
              sx={{
                position: 'absolute',
                top: 4,
                right: 4,
                color: '#888',
                padding: '2px',
                '&:hover': {
                  color: '#f44336',
                  backgroundColor: 'rgba(244, 67, 54, 0.08)',
                },
              }}
              title="Remove"
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          )}
          <div className="ParameterSecondItemTitle">Value:</div>
          <div className="ParameterSecondItemValue">
            {renderValueElement({
              parameterType: this.state.parameter_type,
              value: this.state.value,
              handleChange: this.handleChange,
              readOnly: this.state.readOnly,
              showEnumOptions: true,
              height: '300px',
              className: 'Value',
            })}
          </div>
        </div>
      </div>
    );
  }
}
