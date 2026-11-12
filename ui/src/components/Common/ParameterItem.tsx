import React, { Component, ChangeEvent, FocusEvent } from 'react';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import LinkIcon from '@mui/icons-material/Link';
import renderValueElement from './renderValueElement';
import './ParameterItem.css';

export interface CommonParameterItemProps {
  name: string;
  widget: string;
  reference?: string | null;
  readOnly: boolean;
  parameterType: string;
  onParameterChanged: (name: string, value: any) => void;
  onLinkClick?: (name: string) => void;
  _link_visibility?: boolean;
  value?: any;
}

interface CommonParameterItemState {
  widget: string;
  value: any;
  readOnly: boolean;
  parameterType: string;
}

export default class ParameterItem extends Component<CommonParameterItemProps, CommonParameterItemState> {
  prevVal: any;

  constructor(props: CommonParameterItemProps) {
    super(props);
    this.state = {
      widget: this.props.widget,
      value: this.props.value,
      readOnly: this.props.readOnly,
      parameterType: this.props.parameterType,
    };

    this.handleFocus = this.handleFocus.bind(this);
    this.handleChange = this.handleChange.bind(this);
    this.handleBlur = this.handleBlur.bind(this);
  }

  componentDidUpdate(prevProps: CommonParameterItemProps) {
    if (prevProps.value !== this.props.value || prevProps.readOnly !== this.props.readOnly) {
      this.setState({
        value: this.props.value,
        readOnly: this.props.readOnly,
        widget: this.props.widget,
        parameterType: this.props.parameterType,
      });
    }
  }

  handleChange(event: ChangeEvent<HTMLInputElement>) {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    this.setState({ value });
  }

  handleFocus() {
    this.prevVal = this.state.value;
  }

  handleBlur(event?: FocusEvent<HTMLInputElement>) {
    const target = event ? event.target : null;
    const value = target ? (target.type === 'checkbox' ? target.checked : target.value) : this.state.value;
    if (value !== this.prevVal) {
      this.props.onParameterChanged(this.props.name, value);
    }
  }

  handleLinkClick() {
    if (this.props.onLinkClick) {
      this.props.onLinkClick(this.props.name);
    }
  }

  render() {
    return (
      <div className="ParameterItem">
        <div className="ParameterNameCell">{this.props.widget}</div>
        <div className="ParameterValueCell">
          {!this.props.reference &&
            renderValueElement({
              parameterType: this.state.parameterType,
              value: this.state.value,
              handleFocus: this.handleFocus,
              handleChange: this.handleChange,
              handleBlur: this.handleBlur,
              readOnly: this.state.readOnly,
              className: 'parameter-value',
            })}
          {this.props.reference && <div className="reference">{this.props.reference}</div>}
          {this.props._link_visibility && (
            <Tooltip title="Link parameter">
              <IconButton
                size="small"
                onClick={() => this.handleLinkClick()}
                className="link-button"
                sx={{
                  color: '#888',
                  padding: '2px',
                  marginLeft: '4px',
                  '&:hover': {
                    color: '#2196F3',
                    backgroundColor: 'rgba(33, 150, 243, 0.08)',
                  },
                }}
              >
                <LinkIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </div>
      </div>
    );
  }
}
