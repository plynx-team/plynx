import React, { Component, ChangeEvent } from 'react';
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
      prevProps.value !== this.props.value ||
      prevProps.parameter_type !== this.props.parameter_type ||
      prevProps.name !== this.props.name ||
      prevProps.widget !== this.props.widget ||
      prevProps.readOnly !== this.props.readOnly
    ) {
      this.setState({
        name: this.props.name,
        parameter_type: this.props.parameter_type,
        value: this.props.value,
        widget: this.props.widget,
        readOnly: this.props.readOnly,
        mutable_type: this.props.mutable_type,
        publicable: this.props.publicable,
        removable: this.props.removable,
      });
    }
  }

  handleChange(event: ChangeEvent<any>) {
    if (this.state.readOnly) {
      return;
    }
    const name = event.target.name;
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    let widget = null;
    let newParameterValue = null;

    if (!this.state.mutable_type && (name === 'parameter_type' || name === 'name')) {
      return;
    }

    if (name === 'widget_checkbox') {
      widget = null;
      if (value) {
        widget = this.state.name;
      }
      this.setState({ widget }, () => {
        if (this.props.onChanged) {
          this.props.onChanged(this.props.index, 'widget', widget);
        }
      });
      return;
    } else if (name === 'widget_alias') {
      this.setState({ widget: value }, () => {
        if (this.props.onChanged) {
          this.props.onChanged(this.props.index, 'widget', this.state.widget);
        }
      });
      return;
    } else if (name === 'name' && this.state.widget === this.state.name) {
      widget = value;
      this.setState({ widget }, () => {
        if (this.props.onChanged) {
          this.props.onChanged(this.props.index, 'widget', widget);
        }
      });
    } else if (name === 'parameter_type') {
      if (value !== this.state.parameter_type) {
        newParameterValue = getDefaultParameterValue(value);
        this.setState({ value: newParameterValue });
      }
      this.setState({ parameter_type: value }, () => {
        if (this.props.onChanged) {
          this.props.onChanged(this.props.index, 'value', newParameterValue);
        }
      });
    }

    this.setState({ [name]: value } as any);
    if (name !== 'widget_checkbox' && name !== 'widget_alias' && this.props.onChanged) {
      this.props.onChanged(this.props.index, name, value);
    }
  }

  handleRemoveItem() {
    if (this.props.onRemove) {
      this.props.onRemove(this.props.index);
    }
  }

  render() {
    return (
      <div className={`ParameterListItem parameter-${this.state.name.replace(' ', '_')}`}>
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
              <select
                className="ParameterValue"
                name="parameter_type"
                value={this.state.parameter_type}
                onChange={this.handleChange}
                disabled={Boolean(this.state.readOnly && this.state.mutable_type)}
              >
                {PARAMETER_TYPES.map((description) => (
                  <option value={description.type} key={description.type}>
                    {description.alias}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {this.state.publicable && (
            <div className="ParameterRow">
              <div className="ParameterCellTitle">Widget:</div>
              <div className="ParameterCellValue">
                <input
                  id="checkBox"
                  type="checkbox"
                  name="widget_checkbox"
                  onChange={this.handleChange}
                  checked={this.state.widget !== null && this.state.widget !== undefined}
                  disabled={this.state.readOnly}
                />{' '}
                Public
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
            <div
              className={`Remove${this.state.remove_hover ? ' hover' : ''}`}
              onMouseOver={() => this.setState({ remove_hover: true })}
              onMouseLeave={() => this.setState({ remove_hover: false })}
              onClick={() => this.handleRemoveItem()}
            >
              &#215;
            </div>
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
