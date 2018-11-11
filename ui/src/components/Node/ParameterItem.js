// src/components/About/index.js
import React, { Component } from 'react';
import { PARAMETER_TYPES } from '../../constants.js';
import renderValueElement from '../Common/renderValueElement.js';

import './ParameterItem.css'

export default class ParameterItem extends Component {
  constructor(props) {
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
    };

    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(event) {
    if (this.state.readOnly) {
      return;
    }
    var name = event.target.name;
    var value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    var widget = null;

    // TODO readonly selects
    if (!this.state.mutable_type && (
        name === 'parameter_type' || name === 'name')) {
      return;
    }

    if (name === 'widget_checkbox') {
      widget = null;
      if (value) {
        widget = {alias: this.state.name};
      }
      this.setState({widget: widget },
        () => {
        this.props.onChanged(this.props.index, 'widget', widget)
      });
      return;
    } else if (name === 'widget_alias') {
      this.setState({widget: {alias: value} },
        () => {
        this.props.onChanged(this.props.index, 'widget', this.state.widget)
      });
      return;
    } else if (
        name === 'name' &&
        this.state.widget != null &&
        this.state.widget.alias === this.state.name) {
      // Feature: change alias together with name if the match
      widget = {alias: value};
      this.setState({widget: widget},
        () => {
        this.props.onChanged(this.props.index, 'widget', widget);
      });
    } else if (name === 'parameter_type') {
      if (value !== this.state.parameter_type) {
        var newParameterValue = null;
        switch (value) {
          case 'str':
            newParameterValue = '';
            break;
          case 'int':
            newParameterValue = '0';
            break;
          case 'bool':
            newParameterValue = false;
            break;
          case 'text':
            newParameterValue = '';
            break;
          case 'enum':
            newParameterValue = {index: 0, values: ["enum"]};
            break;
          case 'list_str':
            newParameterValue = [];
            break;
          case 'list_int':
            newParameterValue = [];
            break;
          case 'code':
            newParameterValue = {value: '', mode: 'python'};
            break;
          default:
            throw new Error("Unknown type `" + value + "`");
        }
        this.setState({value: newParameterValue});
      }
      this.setState({parameter_type: value},
        () => {
        this.props.onChanged(this.props.index, 'value', newParameterValue);
      });

    }

    this.setState({[name]: value});
    if (name !== 'widget_checkbox' && name !== 'widget_alias') {
      this.props.onChanged(this.props.index, name, value);
    }
  }

  handleRemoveItem() {
    this.props.onRemove(this.props.index);
  }

  render() {
    return (
      <div className='ParameterListItem'>
        <div className='ParameterFirstItem'>
          <div className='ParameterRow'>
            <div className='ParameterCellTitle'>
              Name:
            </div>
            <div className='ParameterCellValue'>
              <input className='ParameterValue'
                type='text'
                name='name'
                value={this.state.name}
                onChange={this.handleChange}
                readOnly={this.state.readOnly}
              />
            </div>
          </div>

          <div className='ParameterRow'>
            <div className='ParameterCellTitle'>
              Type:
            </div>
            <div className='ParameterCellValue'>
              <select className='ParameterValue'
                type='text'
                name='parameter_type'
                value={this.state.parameter_type}
                onChange={this.handleChange}
                readOnly={this.state.readOnly && this.state.mutable_type}
              >
                {
                  PARAMETER_TYPES.map((description) =>
                    <option
                      value={description.type}
                      key={description.type}
                      >
                      {description.alias}
                      </option>
                  )
                }
              </select>
            </div>
          </div>

          { this.state.publicable &&
            <div className='ParameterRow'>
              <div className='ParameterCellTitle'>
                Widget:
              </div>
              <div className='ParameterCellValue'>
                <input
                  id="checkBox"
                  type="checkbox"
                  name='widget_checkbox'
                  onChange={this.handleChange}
                  checked={this.state.widget != null}
                  readOnly={this.state.readOnly}
                  /> Public
                {
                  this.state.widget != null &&
                  <input className='ParameterValue'
                    type="text"
                    name='widget_alias'
                    value={this.state.widget.alias}
                    onChange={this.handleChange}
                    readOnly={this.state.readOnly}
                  />
                }
              </div>
            </div>
          }
        </div>
        <div className='ParameterSecondItem'>
          {
            (!this.state.readOnly && this.state.removable) &&
            <div
              className={'Remove' + (this.state.remove_hover ? ' hover': '')}
              onMouseOver={() => this.setState({remove_hover: true})}
              onMouseLeave={() => this.setState({remove_hover: false})}
              onClick={() => this.handleRemoveItem()}
            >
              &#215;
            </div>
          }
          <div className='ParameterSecondItemTitle'>
            Value:
          </div>
          <div className='ParameterSecondItemValue'>
            {renderValueElement({
                parameterType: this.state.parameter_type,
                value: this.state.value,
                handleChange: this.handleChange,
                readOnly: this.state.readOnly,
                showEnumOptions:true,
                height: "300px",
                className: "Value",
              }
            )}
          </div>
        </div>
      </div>
    );
  }
}
