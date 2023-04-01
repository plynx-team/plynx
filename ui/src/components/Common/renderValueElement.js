/* eslint max-classes-per-file: 0 */
import React, { Component } from 'react';
import PropTypes from 'prop-types';
import CodeItem from './CodeItem';
import './ValueList.css';
import './NumericInput.css';

function defocusOnEnter(e) {
  if (e.keyCode === 13) {
    e.target.blur();
     // Write you validation logic here
  }
}

function stopPropagation(e) {
  defocusOnEnter(e);
  console.log(e);
  if (e.key === "ArrowUp" || e.key === "ArrowDown") {
    e.stopPropagation();
    e.preventDefault();
    console.log(e.key);
    return false;
  }
  e.stopPropagation();
  return false;
}

export default function renderValueElement(args) {
  const { parameterType, value, handleChange, handleFocus, handleBlur, readOnly } = args;
  const className = args.className ? args.className : "";
  const showEnumOptions = args.showEnumOptions;
  const height = args.height;

  switch (parameterType) {
    case 'str':
      return <input
              autoComplete="off"
              className={className}
              type="text"
              name="value"
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              onKeyDown={defocusOnEnter}
              value={value}
              readOnly={readOnly}
              key={parameterType}
              />;
    case 'password':
      return <input
                autoComplete="off"
                className={className}
                type="password"
                name="value"
                onChange={handleChange}
                onFocus={handleFocus}
                onBlur={handleBlur}
                onKeyDown={defocusOnEnter}
                value={value}
                readOnly={readOnly}
                key={parameterType}
                />;
    case 'int':
      return <input
              className={className}
              type="number"
              name="value"
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              value={value}
              readOnly={readOnly}
              key={parameterType}
              onKeyDown={stopPropagation}
              onWheel={event => event.currentTarget.blur()}
              autoComplete="off"
              />;
    case 'float':
      return <input
              className={className}
              type="number"
              step="any"
              name="value"
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              value={value}
              readOnly={readOnly}
              key={parameterType}
              onKeyDown={stopPropagation}
              onWheel={event => event.currentTarget.blur()}
              autoComplete="off"
              />;

    case 'bool':
      return <div className={className}>
              <input
                type="checkbox"
                name="value"
                onChange={handleChange}
                onFocus={handleFocus}
                onBlur={handleBlur}
                checked={value}
                disabled={readOnly}
                key={parameterType}
                />
              <label className="BoolLabel">
                {value ? 'True' : 'False'}
              </label>
            </div>;
    case 'text':
      return <textarea
              className={className}
              rows='10'
              name="value"
              value={value}
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              readOnly={readOnly}
              key={parameterType}
              />;
    case 'enum':
      return <EnumItem
              className={className}
              name='value'
              value={value}
              onChange={
                (obj) => {
                  handleChange(obj);
                  handleBlur(obj);
                }
              }
              onFocus={handleFocus}
              onBlur={handleBlur}
              readOnly={readOnly}
              key={parameterType}
              showEnumOptions={showEnumOptions || false}
              />;
    case 'list_str':
      return <ValueList
              className={className}
              name='value'
              items={value}
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              readOnly={readOnly}
              key={parameterType}
              parameterType="str"
              />;
    case 'list_int':
      return <ValueList
              className={className}
              name='value'
              items={value}
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              readOnly={readOnly}
              key={parameterType}
              parameterType="int"
              />;
    case 'code':
      return <CodeItem
              className={className}
              name='value'
              value={value}
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              readOnly={readOnly}
              key={parameterType}
              height={height || "200px"}
              showEnumOptions={showEnumOptions || false}
              />;
    default:
      return <div>NULL</div>;
  }
}

export class ValueList extends Component {
  static propTypes = {
    name: PropTypes.string.isRequired,
    parameterType: PropTypes.string.isRequired,
    readOnly: PropTypes.bool.isRequired,
    items: PropTypes.array.isRequired,
    onFocus: PropTypes.func,
    onChange: PropTypes.func,
    onBlur: PropTypes.func,
  };

  constructor(props) {
    super(props);
    this.state = {
      readOnly: this.props.readOnly,
      items: this.props.items
    };

    this.items = this.props.items;
    this.handleFocus = this.handleFocus.bind(this);
    this.handleChange = this.handleChange.bind(this);
    this.handleBlur = this.handleBlur.bind(this);
  }

  notifySetItems() {
    if (this.props.onChange) {
      this.props.onChange({
        target: {
          name: this.props.name,
          value: this.items,
          type: 'list'
        }
      });
    }
  }

  // eslint-disable-next-line no-unused-vars
  handleFocus(index, event) {
    this.prevVal = this.items[index];
  }

  // eslint-disable-next-line no-unused-vars
  handleBlur(index, event) {
    if (this.prevVal !== this.items[index]) {
      this.notifySetItems();
    }
  }

  handleChange(index, event) {
    this.items[index] = event.target.value;
    this.setState({items: this.items});
  }

  handleAddItem() {
    this.items.push("");
    this.setState({items: this.items});
    this.notifySetItems(this.items);
  }

  handleRemoveItem(index) {
    this.items.splice(index, 1);
    this.notifySetItems(this.items);
  }

  render() {
    const self = this;
    return (
      <div className='ValueList'>
        {this.state.items.map((item, index) => (
          <div className="row" key={index}>
          { renderValueElement({
            parameterType: this.props.parameterType,
            value: item,
            handleChange: (event) => {
              self.handleChange(index, event);
            },
            readOnly: this.state.readOnly,
            className: 'ParameterValueCell'
          })
          }
          {!this.state.readOnly &&
            <div
              className={'remove'}
              onClick={() => this.handleRemoveItem(index)}
            > × </div>
          }
          </div>
        ))}

        {!this.state.readOnly &&
          <div
            className={'add'}
            onClick={() => this.handleAddItem()}
          >
              +
          </div>}
      </div>
    );
  }
}

export class EnumItem extends Component {
  static propTypes = {
    name: PropTypes.string.isRequired,
    readOnly: PropTypes.bool.isRequired,
    showEnumOptions: PropTypes.bool.isRequired,
    value: PropTypes.shape({
      values: PropTypes.array.isRequired,
      index: PropTypes.oneOfType([
        PropTypes.number,
        PropTypes.string,
      ]),
    }).isRequired,
    onChange: PropTypes.func.isRequired,
  };

  constructor(props) {
    super(props);
    this.state = {
      readOnly: this.props.readOnly,
      values: this.props.value.values,
      index: this.props.value.index
    };

    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(event) {
    if (this.state.readOnly) {
      return;
    }
    let index = this.state.index;
    let values = this.state.values;

    if (event.target.name === 'values') {
      values = event.target.value;
    } else if (event.target.name === 'index') {
      index = event.target.value;
    }
    index = Math.min(values.length - 1, Math.max(0, index));
    this.setState({index: index});

    if (this.props.onChange) {
      this.props.onChange({
        target: {
          name: this.props.name,
          value: {
            index: index,
            values: values
          },
          type: 'enum'
        }
      });
    }
  }

  render() {
    return (
      <div className='EnumItem'>
        <select className='Index'
            type='text'
            name='index'
            value={this.state.index}
            onChange={this.handleChange}
            disabled={this.state.readOnly}
          >
            {
              this.state.values.map((value, index) => <option
                  value={index}
                  key={index}
                  >
                  {value}
                  </option>
              )
            }
        </select>
        {this.props.showEnumOptions &&
          <div>
            <div>
             Options:
            </div>
            <ValueList
                  name='values'
                  items={this.state.values}
                  onChange={this.handleChange}
                  // readOnly={this.state.readOnly}
                  parameterType="str"
                  />
          </div>
        }
      </div>
    );
  }
}
