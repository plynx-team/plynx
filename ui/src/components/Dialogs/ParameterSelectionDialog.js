import React, { Component } from 'react';
import PropTypes from 'prop-types';
import ParameterItem from '../Common/ParameterItem';
import Dialog from './Dialog';


export default class ParameterSelectionDialog extends Component {
  static propTypes = {
    index: PropTypes.number.isRequired,
    title: PropTypes.string.isRequired,
    onClose: PropTypes.func.isRequired,
    parameters: PropTypes.array.isRequired,
    readOnly: PropTypes.bool.isRequired,
    onIndexChanged: PropTypes.func.isRequired,
  }

  constructor(props) {
    super(props);
    this.state = {
      parameters: props.parameters.filter(
        (parameter) => {
          return parameter.widget !== null;
        }
      ),
      title: props.title,
      index: props.index,
    };
  }

  onIndexChanged(e) {
    if (this.props.readOnly) {
      console.log('Read only');
      return;
    }
    const index = parseInt(e.currentTarget.value, 10);
    this.props.onIndexChanged(index);
    this.setState({index: index});
  }

  render() {
    return (
      <Dialog className='TextViewDialog'
              onClose={() => {
                this.props.onClose();
              }}
              width={500}
              height={300}
              title={this.state.title}
              enableResizing
      >
        <div className="properties-list">
          {
              this.state.parameters.map(
                (parameter, index) => <div className='option-block'
                    key={parameter.name}
                >
                    <div className='radio'>
                        <input
                            type="radio"
                            name="radioname"
                            value={index}
                            checked={index === this.state.index}
                            onChange={(e) => this.onIndexChanged(e)}
                            />
                    </div>

                    <ParameterItem
                      name={parameter.name}
                      widget={parameter.widget}
                      value={parameter.value}
                      parameterType={parameter.parameter_type}
                      readOnly
                      onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
                      onLinkClick={(name) => this.handleLinkClick(name)}
                      />
                </div>
              )
          }
        </div>

      </Dialog>
    );
  }
}
