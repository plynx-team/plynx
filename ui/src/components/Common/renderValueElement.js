// src/components/About/index.js
import React, { Component } from 'react';
import EnumItem from './EnumItem.js';
import CodeItem from './CodeItem.js';
import './ValueList.css';

export default function renderValueElement(args) {
  var { parameterType, value, handleChange, readOnly } = args;
  var className = args.className ? args.className : "";
  var showEnumOptions = args.showEnumOptions;
  var height = args.height;

  switch (parameterType) {
    case 'str':
      return <input
              className={className}
              type="text"
              name="value"
              onChange={handleChange}
              value={value}
              readOnly={readOnly}
              key={parameterType}
              />
    case 'int':
      return <input
              className={className}
              type="number"
              name="value"
              onChange={handleChange}
              value={value}
              readOnly={readOnly}
              key={parameterType}
              />
    case 'bool':
      return <div className={className}>
              <input
                type="checkbox"
                name="value"
                onChange={handleChange}
                checked={value}
                readOnly={readOnly}
                key={parameterType}
                />
              <label className="BoolLabel">
                {value ? 'True' : 'False'}
              </label>
            </div>
    case 'text':
      return <textarea
              className={className}
              rows='2'
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
              showEnumOptions={showEnumOptions}
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
              height={height ? height : "200px"}
              />;
    default:
      return <div>NULL</div>;

  }
}

export class ValueList extends Component {
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
    var items = this.state.items;
    items[index] = event.target.value;
    this.setItems(items);
  }

  handleAddItem() {
    var items = this.state.items;
    items.push("");
    this.setItems(items);
  }

  handleRemoveItem(index) {
    var items = this.state.items;
    items.splice(index, 1);
    this.setItems(items);
  }

  render() {
    var self = this;
    return (
      <div className='ValueList'>
        {this.state.items.map((item, index) => (
          <div className="row" key={index}>
          { renderValueElement({
              parameterType: this.props.parameterType,
              value: item,
              handleChange: (event) => {self.handleChange(index, event)},
              readOnly: this.state.readOnly,
              className: 'ParameterValueCell'
            })
          }
          {!this.state.readOnly &&
            <a
              className={'remove'}
              href={null}
              onClick={() => this.handleRemoveItem(index)}
            > - </a>
          }
          </div>
        ))}

        {!this.state.readOnly &&
          <a
            className={'add'}
            href={null}
            onClick={() => this.handleAddItem()}
          >
              +
          </a>}
      </div>
    );
  }
}
