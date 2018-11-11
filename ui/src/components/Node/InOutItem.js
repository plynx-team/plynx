// src/components/About/index.js
import React, { Component } from 'react';
import { FILE_TYPES } from '../../constants.js'

export default class InOutItem extends Component {
  constructor(props) {
    super(props);
    this.state = {
      name: this.props.name,
      file_types: this.props.fileTypes,
      file_type: this.props.fileType,
      index: this.props.index,
      readOnly: this.props.readOnly,
      min_count: this.props.minCount,
      max_count: this.props.maxCount
    };

    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(event) {
    if (this.state.readOnly) {
      return;
    }
    var name = event.target.name;
    var value = event.target.value;
    if (name === 'file_types') {
      value = [value];
    }
    if (name === 'max_count' || name === 'min_count') {
      value = parseInt(value, 10);
    }
    this.setState({[name]: value});
    this.props.onChanged(this.props.index, name, value);
  }

  handleRemoveItem() {
    this.props.onRemove(this.props.index);
  }

  render() {
    return (
      <div className='InOutItem'>
        {
          !this.state.readOnly &&
          <div
            className={'Remove' + (this.state.remove_hover ? ' hover': '')}
            onMouseOver={() => this.setState({remove_hover: true})}
            onMouseLeave={() => this.setState({remove_hover: false})}
            onClick={() => this.handleRemoveItem()}
          >
            &#215;
          </div>
        }
        <div className='InOutRow'>
          <div className='InOutCellTitle'>
            Name:
          </div>
          <div className='InOutCellValue'>
            <input type="text" className='InOutValue'
              name='name'
              value={this.state.name}
              onChange={this.handleChange}
              readOnly={this.state.readOnly}
            />
          </div>
        </div>
        <div className='InOutRow'>
          <div className='InOutCellTitle'>
            Type:
          </div>
          <div className='InOutCellValue'>
            {
              this.props.varName === 'inputs' &&
              <select className='InOutValue'
                name='file_types'
                value={this.state.file_types[0]}
                onChange={this.handleChange}
                readOnly={this.state.readOnly}
              >
              {
                FILE_TYPES.map((description) =>
                  <option
                    value={description.type}
                    key={description.type}
                    >
                    {description.alias}
                    </option>
                )
              }
              </select>
            }
            {
              this.props.varName === 'outputs' &&
              <select className='InOutValue'
                type='text'
                name='file_type'
                value={this.state.file_type}
                onChange={this.handleChange}
                readOnly={this.state.readOnly}
              >
              {
                FILE_TYPES.map((description) =>
                  <option
                    value={description.type}
                    key={description.type}
                    >
                    {description.alias}
                    </option>
                )
              }
              </select>
            }

          </div>
        </div>

        {! (this.state.min_count === undefined) &&
          <div className='InOutRow'>
            <div className='InOutCellTitle'>
              Count:
            </div>
            <div className='InOutCellValue'>
              <div className='InOutValue'>
                <div className='CountsBlock'>
                  <div className='Cell'>min</div>
                  <input className='CellValue'
                          type="number"
                          name="min_count"
                          onChange={this.handleChange}
                          value={this.state.min_count}
                          readOnly={this.state.readOnly}
                          />
                  <div className='Cell'>max</div>
                  <input className='CellValue'
                          type="number"
                          name="max_count"
                          onChange={this.handleChange}
                          value={this.state.max_count}
                          readOnly={this.state.readOnly}
                          />
                 </div>
              </div>

            </div>
          </div>
        }

      </div>
    );
  }
}
