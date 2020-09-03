import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Icon from '../Common/Icon';
import { PluginsConsumer } from '../../contexts';
import OutputItem from '../Graph/OutputItem';


export default class InOutItem extends Component {
  static propTypes = {
    index: PropTypes.number,
    readOnly: PropTypes.bool,
    name: PropTypes.string,
    onChanged: PropTypes.func,
    onRemove: PropTypes.func,
    item: PropTypes.object.isRequired,
    nodeKind: PropTypes.string.isRequired,
    onPreview: PropTypes.func.isRequired,
  };

  constructor(props) {
    super(props);
    this.item = this.props.item;
    this.state = {
      item: this.props.item,
      index: this.props.index,
      readOnly: this.props.readOnly,
    };

    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(event) {
    if (this.state.readOnly) {
      return;
    }
    const name = event.target.name;
    let value = event.target.value;
    if (name === 'is_array') {
      value = event.target.checked;
    } else if (name === 'min_count') {
      value = parseInt(value, 10);
    }
    this.item[name] = value;
    this.setState({item: this.item});
    this.props.onChanged(this.props.index, name, value);
  }

  handleRemoveItem() {
    this.props.onRemove(this.props.index);
  }

  handlePreview(previewData) {
    this.props.onPreview(previewData);
  }

  render() {
    return (
      <div className='InOutItem'>
        {
          !this.state.readOnly &&
          <div
            className={'Remove' + (this.state.remove_hover ? ' hover' : '')}
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
              value={this.state.item.name}
              onChange={this.handleChange}
              readOnly={this.state.readOnly}
            />
          </div>
        </div>
        <div className='InOutRow'>
          <div className='InOutCellTitle'>
            Type:
          </div>
          <PluginsConsumer>
          { plugins_dict => <div className='InOutCellValue'>

              <select className='InOutValue'
                type='text'
                name='file_type'
                value={this.state.item.file_type}
                onChange={this.handleChange}
                readOnly={this.state.readOnly}
              >
              {
                plugins_dict.operations_dict[this.props.nodeKind].resources.map((description) => <option
                    value={description.kind}
                    key={description.kind}
                    >
                    {description.title}
                    </option>
                )
              }
              </select>
              <Icon
                type_descriptor={plugins_dict.resources_dict[this.state.item.file_type]}
              />
            </div>
          }
          </PluginsConsumer>
        </div>

        <div className='InOutRow'>
          <div className='InOutCellTitle'>
            Array:
          </div>
          <div className='InOutCellValue'>
            <div className='InOutValue'>
                <input
                  type="checkbox"
                  name="is_array"
                  onChange={this.handleChange}
                  defaultChecked={this.state.item.is_array}
                  readOnly={this.state.readOnly}
                  >
                </input>
                <label className="BoolLabel">
                  {this.state.item.is_array ? 'True' : 'False'}
                </label>
            </div>
          </div>
        </div>

        {this.state.item.is_array &&
        <div className='InOutRow'>
          <div className='InOutCellTitle'>
            Min size
          </div>
          <div className='InOutCellValue'>
            <div className='InOutValue'>
                <input className='CellValue'
                    type="number"
                    name="min_count"
                    min="0"
                    onChange={this.handleChange}
                    value={this.state.item.min_count}
                    readOnly={this.state.readOnly}
                    />
            </div>
          </div>
        </div>
        }

        {this.state.item.values.map((resource_id) => <OutputItem
              item={this.state.item}
              key={resource_id}
              onPreview={(previewData) => this.handlePreview(previewData)}
              />
        )}

      </div>
    );
  }
}
