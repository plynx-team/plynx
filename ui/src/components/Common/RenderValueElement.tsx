import React, { Component, ChangeEvent, FocusEvent, KeyboardEvent, WheelEvent } from 'react';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Slider from '@mui/material/Slider';
import CloseIcon from '@mui/icons-material/Close';
import AddIcon from '@mui/icons-material/Add';
import ValueCodeItem from './ValueCodeItem';
import ValueColorItem from './ValueColorItem';
import './ValueList.css';
import './NumericInput.css';

function defocusOnEnter(e: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) {
  if (e.key === 'Enter' || e.keyCode === 13) {
    (e.target as HTMLElement).blur();
  }
}

function stopPropagation(e: KeyboardEvent<HTMLInputElement>) {
  defocusOnEnter(e);
  if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    e.stopPropagation();
    e.preventDefault();
    return false;
  }
  e.stopPropagation();
  return false;
}

export interface RenderValueElementArgs {
  parameterType: string;
  value: any;
  handleChange?: (event: any) => void;
  handleFocus?: (event: any) => void;
  handleBlur?: (event: any) => void;
  readOnly?: boolean;
  className?: string;
  showEnumOptions?: boolean;
  height?: string;
  min?: number;
  max?: number;
  step?: number;
}

export default function renderValueElement(args: RenderValueElementArgs): React.ReactNode {
  const { parameterType, value, handleChange, handleFocus, handleBlur, readOnly } = args;
  const className = args.className || '';
  const showEnumOptions = args.showEnumOptions;
  const height = args.height;

  switch (parameterType) {
    case 'str':
      return (
        <input
          autoComplete="off"
          className={className}
          type="text"
          name="value"
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={defocusOnEnter}
          value={value ?? ''}
          readOnly={readOnly}
          key={parameterType}
        />
      );
    case 'password':
      return (
        <input
          autoComplete="off"
          className={className}
          type="password"
          name="value"
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={defocusOnEnter}
          value={value ?? ''}
          readOnly={readOnly}
          key={parameterType}
        />
      );
    case 'int':
      return (
        <input
          className={className}
          type="number"
          name="value"
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          value={value ?? 0}
          readOnly={readOnly}
          key={parameterType}
          onKeyDown={stopPropagation}
          onWheel={(event: WheelEvent<HTMLInputElement>) => event.currentTarget.blur()}
          autoComplete="off"
        />
      );
    case 'float':
      return (
        <input
          className={className}
          type="number"
          step="any"
          name="value"
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          value={value ?? 0.0}
          readOnly={readOnly}
          key={parameterType}
          onKeyDown={stopPropagation}
          onWheel={(event: WheelEvent<HTMLInputElement>) => event.currentTarget.blur()}
          autoComplete="off"
        />
      );
    case 'slider':
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%', paddingX: 1 }} key={parameterType}>
          <Slider
            size="small"
            value={typeof value === 'number' ? value : Number(value) || 0}
            min={args.min ?? 0}
            max={args.max ?? 100}
            step={args.step ?? 1}
            disabled={readOnly}
            onChange={(_e, val) => {
              if (handleChange) {
                handleChange({ target: { name: 'value', value: val, type: 'float' } });
              }
            }}
            valueLabelDisplay="auto"
            sx={{ color: '#2196F3' }}
          />
          <Typography variant="caption" sx={{ color: '#eee', minWidth: 35, textAlign: 'right' }}>
            {value}
          </Typography>
        </Box>
      );
    case 'bool':
      return (
        <FormControlLabel
          key={parameterType}
          className={className}
          control={
            <Switch
              size="small"
              checked={Boolean(value)}
              disabled={readOnly}
              onChange={(e) => {
                if (handleChange) {
                  handleChange({
                    target: {
                      name: 'value',
                      value: e.target.checked,
                      type: 'bool',
                    },
                  });
                }
              }}
              color="primary"
            />
          }
          label={
            <Typography variant="body2" sx={{ color: '#eee', fontSize: 'var(--font-size-base)' }}>
              {value ? 'True' : 'False'}
            </Typography>
          }
          sx={{
            margin: '4px 0 4px 6px',
            '& .MuiFormControlLabel-label': {
              marginLeft: '6px',
            },
          }}
        />
      );
    case 'text':
      return (
        <textarea
          className={className}
          rows={10}
          name="value"
          value={value ?? ''}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          readOnly={readOnly}
          key={parameterType}
        />
      );
    case 'enum':
      return (
        <EnumItem
          className={className}
          name="value"
          value={value}
          onChange={(obj: any) => {
            if (handleChange) handleChange(obj);
            if (handleBlur) handleBlur(obj);
          }}
          onFocus={handleFocus}
          onBlur={handleBlur}
          readOnly={Boolean(readOnly)}
          key={parameterType}
          showEnumOptions={showEnumOptions || false}
        />
      );
    case 'list_str':
      return (
        <ValueList
          className={className}
          name="value"
          items={Array.isArray(value) ? value : []}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          readOnly={Boolean(readOnly)}
          key={parameterType}
          parameterType="str"
        />
      );
    case 'list_int':
      return (
        <ValueList
          className={className}
          name="value"
          items={Array.isArray(value) ? value : []}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          readOnly={Boolean(readOnly)}
          key={parameterType}
          parameterType="int"
        />
      );
    case 'code':
      return (
        <ValueCodeItem
          name="value"
          value={value}
          onChange={handleChange || (() => {})}
          readOnly={Boolean(readOnly)}
          key={parameterType}
          height={height || '200px'}
          showEnumOptions={showEnumOptions || false}
        />
      );
    case 'color':
      return (
        <ValueColorItem
          name="value"
          value={value}
          onChange={handleBlur || (() => {})}
          key={parameterType}
        />
      );
    default:
      return <div>NULL</div>;
  }
}

export interface ValueListProps {
  name: string;
  parameterType: string;
  readOnly: boolean;
  items: any[];
  className?: string;
  onFocus?: (e: any) => void;
  onChange?: (e: any) => void;
  onBlur?: (e: any) => void;
}

interface ValueListState {
  readOnly: boolean;
  items: any[];
}

export class ValueList extends Component<ValueListProps, ValueListState> {
  items: any[];
  prevVal: any;

  constructor(props: ValueListProps) {
    super(props);
    this.items = [...(props.items || [])];
    this.state = {
      readOnly: this.props.readOnly,
      items: this.items,
    };

    this.handleFocus = this.handleFocus.bind(this);
    this.handleChange = this.handleChange.bind(this);
    this.handleBlur = this.handleBlur.bind(this);
  }

  componentDidUpdate(prevProps: ValueListProps) {
    if (prevProps.items !== this.props.items) {
      this.items = [...(this.props.items || [])];
      this.setState({ items: this.items });
    }
  }

  notifySetItems(_newItems?: any[]) {
    if (this.props.onChange) {
      this.props.onChange({
        target: {
          name: this.props.name,
          value: this.items,
          type: 'list',
        },
      });
    }
  }

  handleFocus(index: number, _event?: FocusEvent<any>) {
    this.prevVal = this.items[index];
  }

  handleBlur(index: number, _event?: FocusEvent<any>) {
    if (this.prevVal !== this.items[index]) {
      this.notifySetItems();
    }
  }

  handleChange(index: number, event: ChangeEvent<HTMLInputElement>) {
    this.items[index] = event.target.value;
    this.setState({ items: [...this.items] });
  }

  handleAddItem() {
    this.items.push('');
    this.setState({ items: [...this.items] });
    this.notifySetItems(this.items);
  }

  handleRemoveItem(index: number) {
    this.items.splice(index, 1);
    this.setState({ items: [...this.items] });
    this.notifySetItems(this.items);
  }

  render() {
    return (
      <div className="ValueList">
        {this.state.items.map((item, index) => (
          <div className="row" key={index} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            {renderValueElement({
              parameterType: this.props.parameterType,
              value: item,
              handleChange: (event) => {
                this.handleChange(index, event);
              },
              readOnly: this.state.readOnly,
              className: 'ParameterValueCell',
            })}
            {!this.state.readOnly && (
              <IconButton
                size="small"
                onClick={() => this.handleRemoveItem(index)}
                sx={{
                  color: '#888',
                  padding: '2px',
                  '&:hover': {
                    color: '#f44336',
                    backgroundColor: 'rgba(244, 67, 54, 0.08)',
                  },
                }}
                title="Remove item"
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            )}
          </div>
        ))}

        {!this.state.readOnly && (
          <Button
            size="small"
            startIcon={<AddIcon fontSize="small" />}
            onClick={() => this.handleAddItem()}
            sx={{
              color: '#2196F3',
              textTransform: 'none',
              fontSize: 'var(--font-size-base)',
              padding: '2px 8px',
              marginTop: 0.5,
              alignSelf: 'flex-start',
            }}
          >
            Add item
          </Button>
        )}
      </div>
    );
  }
}

export interface EnumItemProps {
  name: string;
  readOnly: boolean;
  showEnumOptions: boolean;
  value: {
    values: any[];
    index: number | string;
  };
  onChange?: (e: any) => void;
  onFocus?: (e: any) => void;
  onBlur?: (e: any) => void;
  className?: string;
}

interface EnumItemState {
  readOnly: boolean;
  values: any[];
  index: number | string;
}

export class EnumItem extends Component<EnumItemProps, EnumItemState> {
  constructor(props: EnumItemProps) {
    super(props);
    const initial = props.value || { values: ['enum'], index: 0 };
    this.state = {
      readOnly: this.props.readOnly,
      values: initial.values || ['enum'],
      index: initial.index ?? 0,
    };

    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(event: any) {
    if (this.state.readOnly) {
      return;
    }
    let index = this.state.index;
    let values = this.state.values;

    if (event.target.name === 'values') {
      values = event.target.value;
    } else if (event.target.name === 'index') {
      index = Number(event.target.value);
    }
    const numericIndex = typeof index === 'number' ? index : parseInt(String(index), 10) || 0;
    const clampedIndex = Math.min(values.length - 1, Math.max(0, numericIndex));
    this.setState({ index: clampedIndex, values });

    if (this.props.onChange) {
      this.props.onChange({
        target: {
          name: this.props.name,
          value: {
            index: clampedIndex,
            values,
          },
          type: 'enum',
        },
      });
    }
  }

  render() {
    return (
      <div className="EnumItem">
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <Select
            className="Index"
            value={Number(this.state.index)}
            onChange={(e) => this.handleChange({ target: { name: 'index', value: e.target.value } })}
            disabled={this.state.readOnly}
            sx={{
              height: 28,
              fontSize: 'var(--font-size-base)',
              color: '#fff',
              backgroundColor: '#262626',
              '& .MuiSelect-select': {
                paddingY: '2px',
                paddingLeft: '8px',
              },
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: '#444',
              },
            }}
          >
            {this.state.values.map((val, idx) => (
              <MenuItem value={idx} key={idx} sx={{ fontSize: 'var(--font-size-base)' }}>
                {val}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        {this.props.showEnumOptions && (
          <Box sx={{ marginTop: 1 }}>
            <Typography variant="body2" sx={{ color: '#aaa', fontWeight: 'var(--font-weight-semibold)', fontSize: 'var(--font-size-base)' }}>
              Options:
            </Typography>
            <ValueList
              name="values"
              items={this.state.values}
              onChange={this.handleChange}
              readOnly={this.state.readOnly}
              parameterType="str"
            />
          </Box>
        )}
      </div>
    );
  }
}
