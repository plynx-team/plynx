import React, { Component } from 'react';
import PropTypes from 'prop-types';
import renderValueElement from './renderValueElement';
import './ParameterItem.css';

export default class ParameterItem extends Component {
  static propTypes = {
    name: PropTypes.string,
    widget: PropTypes.string.isRequired,
    reference: PropTypes.string,
    readOnly: PropTypes.bool.isRequired,
    parameterType: PropTypes.string.isRequired,
    onParameterChanged: PropTypes.func.isRequired,
    onLinkClick: PropTypes.func,
    _link_visibility: PropTypes.bool,
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
      widget: this.props.widget,
      value: this.props.value,
      readOnly: this.props.readOnly,
      parameterType: this.props.parameterType,
    };

    this.handleFocus = this.handleFocus.bind(this);
    this.handleChange = this.handleChange.bind(this);
    this.handleBlur = this.handleBlur.bind(this);
  }

  handleChange(event) {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    this.setState({value: value});
  }

  handleFocus(event) {
    this.prevVal = this.state.value;
  }

  handleBlur(event) {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    if (value !== this.prevVal) {
      this.props.onParameterChanged(this.props.name, value);
    }
  }

  handleLinkClick() {
    this.props.onLinkClick(this.props.name);
  }

  render() {
    return (
      <div className='ParameterItem'>
        <div className='ParameterNameCell'>
          {this.props.widget}
        </div>
        <div className='ParameterValueCell'>
            { !this.props.reference &&
                renderValueElement({
                  parameterType: this.state.parameterType,
                  value: this.state.value,
                  handleFocus: this.handleFocus,
                  handleChange: this.handleChange,
                  handleBlur: this.handleBlur,
                  readOnly: this.state.readOnly,
                  className: 'parameter-value',
                }
                )
            }
            {
                this.props.reference && <div className='reference'>{this.props.reference}</div>
            }
            {this.props._link_visibility &&
            <div
                className={'link-button control-button'}
                onClick={() => {
                  this.handleLinkClick();
                }}
            >
              <img
                className={'icon'}
                src={"/icons/link-2.svg"}
                alt="link"
                />
            </div>
            }
        </div>


      </div>
    );
  }
}
