import React, { Component } from 'react';
import PropTypes from 'prop-types';
import EnumItem from './EnumItem';  // eslint-disable-line import/no-cycle
import CodeItem from './CodeItem';
import './ValueList.css';
import './NumericInput.css';


function stopPropagation(e) {
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
  const { parameterType, value, handleChange, readOnly } = args;
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
              readOnly={readOnly}
              key={parameterType}
              />;
    case 'enum':
      return <EnumItem
              className={className}
              name='value'
              value={value}
              onChange={handleChange}
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
    onChange: PropTypes.func,
  }

  constructor(props) {
    super(props);
    this.state = {
      readOnly: this.props.readOnly,
      items: this.props.items
    };

    this.handleChange = this.handleChange.bind(this);
  }

  setItems(items) {
    this.setState({items: items});
    if (this.props.onChange) {
      this.props.onChange({
        target: {
          name: this.props.name,
          value: items,
          type: 'list'
        }
      });
    }
  }

  handleChange(index, event) {
    const items = this.state.items;
    items[index] = event.target.value;
    this.setItems(items);
  }

  handleAddItem() {
    const items = this.state.items;
    items.push("");
    this.setItems(items);
  }

  handleRemoveItem(index) {
    const items = this.state.items;
    items.splice(index, 1);
    this.setItems(items);
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
