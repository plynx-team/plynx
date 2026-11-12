import React, { Component, ChangeEvent, FocusEvent, KeyboardEvent, WheelEvent } from 'react';
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
    case 'bool':
      return (
        <div className={className}>
          <input
            type="checkbox"
            name="value"
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            checked={Boolean(value)}
            disabled={readOnly}
            key={parameterType}
          />
          <label className="BoolLabel">{value ? 'True' : 'False'}</label>
        </div>
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
          <div className="row" key={index}>
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
              <div
                className="remove"
                onClick={() => this.handleRemoveItem(index)}
              >
                {' '}
                ×{' '}
              </div>
            )}
          </div>
        ))}

        {!this.state.readOnly && (
          <div className="add" onClick={() => this.handleAddItem()}>
            +
          </div>
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
        <select
          className="Index"
          name="index"
          value={this.state.index}
          onChange={this.handleChange}
          disabled={this.state.readOnly}
        >
          {this.state.values.map((val, idx) => (
            <option value={idx} key={idx}>
              {val}
            </option>
          ))}
        </select>
        {this.props.showEnumOptions && (
          <div>
            <div>Options:</div>
            <ValueList
              name="values"
              items={this.state.values}
              onChange={this.handleChange}
              readOnly={this.state.readOnly}
              parameterType="str"
            />
          </div>
        )}
      </div>
    );
  }
}
