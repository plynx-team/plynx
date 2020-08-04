import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { ValueList } from './renderValueElement';  // eslint-disable-line import/no-cycle

export default class EnumItem extends Component {
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
  }

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
