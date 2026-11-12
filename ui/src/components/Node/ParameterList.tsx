import React, { Component } from 'react';
import ParameterItem from './ParameterItem';
import ReorderableList from '../Common/ReorderableList';
import './Parameter.css';

export interface ParameterListItemData {
  name: string;
  parameter_type: string;
  value: any;
  widget?: string | null;
  _key?: string;
  removable?: boolean;
  publicable?: boolean;
  mutable_type?: boolean;
  [key: string]: any;
}

export interface ParameterListProps {
  items: ParameterListItemData[];
  readOnly?: boolean;
  onChanged: (items: ParameterListItemData[]) => void;
}

interface ParameterListState {
  items: ParameterListItemData[];
  readOnly: boolean;
}

export default class ParameterList extends Component<ParameterListProps, ParameterListState> {
  counter: number = 0;

  constructor(props: ParameterListProps) {
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

  componentDidUpdate(prevProps: ParameterListProps) {
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

  handleAddItem() {
    const items = [...this.state.items];
    items.push({
      name: `parameter_${this.counter}`,
      parameter_type: 'str',
      value: '',
      widget: null,
      _key: String(this.counter),
      removable: true,
      publicable: true,
      mutable_type: true,
    });
    this.counter += 1;
    this.setState({ items });
    this.props.onChanged(items);
  }

  render() {
    return (
      <ReorderableList<ParameterListItemData>
        items={this.state.items}
        readOnly={this.state.readOnly}
        onChanged={(items) => {
          this.setState({ items });
          this.props.onChanged(items);
        }}
        onAddItem={() => this.handleAddItem()}
        addButtonText="Add Parameter"
        className="ParameterList"
        renderItem={(item, index) => (
          <ParameterItem
            key={item._key || index}
            name={item.name}
            widget={item.widget}
            parameter_type={item.parameter_type}
            index={index}
            value={item.value}
            readOnly={this.state.readOnly}
            removable={item.removable !== false}
            publicable={item.publicable !== false}
            mutable_type={item.mutable_type !== false}
            onChanged={(idx, name, val) => this.handleChanged(idx, name, val)}
            onRemove={(idx) => this.handleRemove(idx)}
          />
        )}
      />
    );
  }
}
