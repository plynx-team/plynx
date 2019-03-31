import React, { Component } from 'react';
import PropTypes from 'prop-types';
import renderValueElement from './renderValueElement';
import './ParameterItem.css';

export default class ParameterItem extends Component {
  static propTypes = {
    name: PropTypes.string.isRequired,
    alias: PropTypes.string.isRequired,
    readOnly: PropTypes.bool.isRequired,
    parameterType: PropTypes.string.isRequired,
    onParameterChanged: PropTypes.func.isRequired,
    value: PropTypes.oneOfType([
      PropTypes.object,
      PropTypes.string,
      PropTypes.bool,
      PropTypes.number,
      PropTypes.array,
    ]),
  }

  constructor(props) {
    super(props);
    this.state = {
      name: this.props.name,
      alias: this.props.alias,
      value: this.props.value,
      readOnly: this.props.readOnly,
      parameterType: this.props.parameterType
    };

    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(event) {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    this.setState({value: value});
    this.props.onParameterChanged(this.props.name, value);
  }

  render() {
    return (
      <div className='ParameterItem'>
        <div className='ParameterNameCell'>
          {this.state.alias}
        </div>
        {renderValueElement({
          parameterType: this.state.parameterType,
          value: this.state.value,
          handleChange: this.handleChange,
          readOnly: this.state.readOnly,
          className: 'ParameterValueCell'
        }
        )}
      </div>
    );
  }
}
