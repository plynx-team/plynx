import React, { Component, ChangeEvent } from 'react';
import Icon from '../Common/Icon';
import { PluginsConsumer } from '../../contexts';
import OutputItem from '../Graph/OutputItem';
import { PreviewData, PluginsDict } from '../../types';

export interface InOutItemData {
  name: string;
  file_type: string;
  is_array?: boolean;
  min_count?: number;
  values?: any[];
  _key?: string;
  [key: string]: any;
}

export interface InOutItemProps {
  index: number;
  readOnly?: boolean;
  name?: string;
  onChanged?: (index: number, name: string, value: any) => void;
  onRemove?: (index: number) => void;
  item: InOutItemData;
  nodeKind: string;
  onPreview: (previewData: PreviewData) => void;
  _key?: string;
}

interface InOutItemState {
  item: InOutItemData;
  index: number;
  readOnly?: boolean;
  remove_hover?: boolean;
}

export default class InOutItem extends Component<InOutItemProps, InOutItemState> {
  item: InOutItemData;

  constructor(props: InOutItemProps) {
    super(props);
    this.item = { ...this.props.item };
    this.state = {
      item: this.item,
      index: this.props.index,
      readOnly: this.props.readOnly,
      remove_hover: false,
    };

    this.handleChange = this.handleChange.bind(this);
  }

  componentDidUpdate(prevProps: InOutItemProps) {
    if (prevProps.item !== this.props.item || prevProps.readOnly !== this.props.readOnly) {
      this.item = { ...this.props.item };
      this.setState({
        item: this.item,
        readOnly: this.props.readOnly,
      });
    }
  }

  handleChange(event: ChangeEvent<any>) {
    if (this.state.readOnly) {
      return;
    }
    const name = event.target.name;
    let value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    if (name === 'is_array') {
      value = event.target.checked;
    } else if (name === 'min_count') {
      value = parseInt(value, 10);
    }
    this.item[name] = value;
    this.setState({ item: { ...this.item } });
    if (this.props.onChanged) {
      this.props.onChanged(this.props.index, name, value);
    }
  }

  handleRemoveItem() {
    if (this.props.onRemove) {
      this.props.onRemove(this.props.index);
    }
  }

  handlePreview(previewData: PreviewData) {
    this.props.onPreview(previewData);
  }

  render() {
    const values = this.state.item.values || [];

    return (
      <div className="InOutItem">
        {!this.state.readOnly && (
          <div
            className={`Remove${this.state.remove_hover ? ' hover' : ''}`}
            onMouseOver={() => this.setState({ remove_hover: true })}
            onMouseLeave={() => this.setState({ remove_hover: false })}
            onClick={() => this.handleRemoveItem()}
          >
            &#215;
          </div>
        )}
        <div className="InOutRow">
          <div className="InOutCellTitle">Name:</div>
          <div className="InOutCellValue">
            <input
              type="text"
              className="InOutValue"
              name="name"
              value={this.state.item.name}
              onChange={this.handleChange}
              readOnly={this.state.readOnly}
            />
          </div>
        </div>
        <div className="InOutRow">
          <div className="InOutCellTitle">Type:</div>
          <PluginsConsumer>
            {(plugins_dict: PluginsDict) => {
              const op = plugins_dict.operations_dict?.[this.props.nodeKind];
              const resources: any[] = op?.resources || [];
              const resourceDesc = plugins_dict.resources_dict[this.state.item.file_type];

              return (
                <div className="InOutCellValue">
                  <select
                    className="InOutValue"
                    name="file_type"
                    value={this.state.item.file_type}
                    onChange={this.handleChange}
                    disabled={this.state.readOnly}
                  >
                    {resources.map((description: any) => (
                      <option value={description.kind} key={description.kind}>
                        {description.title}
                      </option>
                    ))}
                  </select>
                  {resourceDesc && (
                    <Icon type_descriptor={resourceDesc} />
                  )}
                </div>
              );
            }}
          </PluginsConsumer>
        </div>

        <div className="InOutRow">
          <div className="InOutCellTitle">Array:</div>
          <div className="InOutCellValue">
            <div className="InOutValue">
              <input
                type="checkbox"
                name="is_array"
                onChange={this.handleChange}
                checked={Boolean(this.state.item.is_array)}
                disabled={this.state.readOnly}
              />
              <label className="BoolLabel">
                {this.state.item.is_array ? 'True' : 'False'}
              </label>
            </div>
          </div>
        </div>

        {this.state.item.is_array && (
          <div className="InOutRow">
            <div className="InOutCellTitle">Min size</div>
            <div className="InOutCellValue">
              <div className="InOutValue">
                <input
                  className="CellValue"
                  type="number"
                  name="min_count"
                  min="0"
                  onChange={this.handleChange}
                  value={this.state.item.min_count ?? 0}
                  readOnly={this.state.readOnly}
                />
              </div>
            </div>
          </div>
        )}

        {values.map((resource_id: any) => (
          <OutputItem
            item={this.state.item as any}
            key={resource_id}
            onPreview={(previewData) => this.handlePreview(previewData)}
          />
        ))}
      </div>
    );
  }
}
