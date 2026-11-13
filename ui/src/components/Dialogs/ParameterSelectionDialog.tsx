import React, { Component, ChangeEvent } from 'react';
import Radio from '@mui/material/Radio';
import ParameterItem from '../Common/ParameterItem';
import Dialog from './Dialog';
import { NodeParameter } from '../../types';

export interface ParameterSelectionDialogProps {
  index: number;
  title: string;
  onClose: () => void;
  parameters: NodeParameter[];
  readOnly: boolean;
  onIndexChanged: (index: number) => void;
}

interface ParameterSelectionDialogState {
  parameters: NodeParameter[];
  title: string;
  index: number;
}

export default class ParameterSelectionDialog extends Component<
  ParameterSelectionDialogProps,
  ParameterSelectionDialogState
> {
  constructor(props: ParameterSelectionDialogProps) {
    super(props);
    this.state = {
      parameters: props.parameters.filter(
        (parameter) => parameter.widget !== null && parameter.widget !== undefined
      ),
      title: props.title,
      index: props.index,
    };
  }

  onIndexChanged(e: ChangeEvent<HTMLInputElement>) {
    if (this.props.readOnly) {
      console.log('Read only');
      return;
    }
    const index = parseInt(e.currentTarget.value, 10);
    this.props.onIndexChanged(index);
    this.setState({ index });
  }

  handleParameterChanged(_name: string, _value: any) {}

  handleLinkClick(_name: string) {}

  render() {
    return (
      <Dialog
        className="TextViewDialog"
        onClose={() => {
          this.props.onClose();
        }}
        width={500}
        height={300}
        title={this.state.title}
        enableResizing
      >
        <div className="properties-list">
          {this.state.parameters.map((parameter, index) => (
            <div className="option-block" key={parameter.name} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div className="radio">
                <Radio
                  name="radioname"
                  value={index}
                  checked={index === this.state.index}
                  onChange={(e) => this.onIndexChanged(e)}
                  size="small"
                  disabled={this.props.readOnly}
                  sx={{
                    color: '#888',
                    '&.Mui-checked': {
                      color: '#2196F3',
                    },
                  }}
                />
              </div>

              <ParameterItem
                name={parameter.name}
                widget={parameter.widget || parameter.name}
                value={parameter.value}
                parameterType={parameter.parameter_type}
                readOnly
                onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
                onLinkClick={(name) => this.handleLinkClick(name)}
              />
            </div>
          ))}
        </div>
      </Dialog>
    );
  }
}
