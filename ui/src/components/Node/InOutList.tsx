import React, { Component } from 'react';
import InOutItem, { InOutItemData } from './InOutItem';
import ReorderableList from '../Common/ReorderableList';
import { PluginsConsumer } from '../../contexts';
import { PreviewData, PluginsDict } from '../../types';
import './InOut.css';

export interface InOutListProps {
  items: InOutItemData[];
  readOnly?: boolean;
  varName: string;
  nodeKind: string;
  onChanged: (items: InOutItemData[]) => void;
  onPreview: (previewData: PreviewData) => void;
}

interface InOutListState {
  items: InOutItemData[];
  readOnly: boolean;
}

export default class InOutList extends Component<InOutListProps, InOutListState> {
  counter: number = 0;

  constructor(props: InOutListProps) {
    super(props);
    const items = props.items || [];
    items.forEach((obj) => {
      obj._key = String(this.counter);
      this.counter += 1;
    });
    this.state = {
      items,
      readOnly: Boolean(this.props.readOnly),
    };
  }

  componentDidUpdate(prevProps: InOutListProps) {
    if (prevProps.items !== this.props.items || prevProps.readOnly !== this.props.readOnly) {
      this.setState({
        items: this.props.items,
        readOnly: Boolean(this.props.readOnly),
      });
    }
  }

  handleChanged(index: number, name: string, value: any) {
    const items = [...this.state.items];
    items[index] = { ...items[index], [name]: value };
    this.setState({ items });
    this.props.onChanged(items);
  }

  handleRemove(index: number) {
    const items = [...this.state.items];
    items.splice(index, 1);
    this.setState({ items });
    this.props.onChanged(items);
  }

  handleAddItem(resourcesDict: Record<string, any>) {
    const items = [...this.state.items];
    const firstResourceKey = Object.keys(resourcesDict)[0] || 'file';
    items.push({
      name: `${this.props.varName}_${this.counter}`,
      file_type: firstResourceKey,
      values: [],
      min_count: 1,
      is_array: false,
      _key: String(this.counter),
    });
    this.counter += 1;
    this.setState({ items });
    this.props.onChanged(items);
  }

  render() {
    return (
      <PluginsConsumer>
        {(plugins_dict: PluginsDict) => {
          const op = plugins_dict.operations_dict?.[this.props.nodeKind];
          const resourcesDict = op?.resources_dict || plugins_dict.resources_dict || {};

          return (
            <ReorderableList<InOutItemData>
              items={this.state.items}
              readOnly={this.state.readOnly}
              onChanged={(items) => {
                this.setState({ items });
                this.props.onChanged(items);
              }}
              onAddItem={() => this.handleAddItem(resourcesDict)}
              addButtonText={`Add ${this.props.varName}`}
              className="InOutList"
              renderItem={(item, index) => (
                <InOutItem
                  key={item._key || index}
                  item={item}
                  index={index}
                  readOnly={this.state.readOnly}
                  nodeKind={this.props.nodeKind}
                  onChanged={(idx, name, val) => this.handleChanged(idx, name, val)}
                  onRemove={(idx) => this.handleRemove(idx)}
                  onPreview={this.props.onPreview}
                />
              )}
            />
          );
        }}
      </PluginsConsumer>
    );
  }
}
