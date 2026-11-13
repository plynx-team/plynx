import React, { Component, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { COLLECTIONS } from '../../constants';
import ParameterItem from '../Common/ParameterItem';
import makePropertiesBox from '../Common/PropertiesBox';
import './NodeProperties.css';
import { utcTimeToLocal } from '../../utils';
import { ExecutorInfo } from '../../types';

function makeKeyValueRow(name: string, value: ReactNode, key: string) {
  return (
    <div className="ParameterItem" key={key}>
      <div className="ParameterNameCell">{name}</div>
      <div className="ParameterValueCell">{value}</div>
    </div>
  );
}

export interface NodePropertiesProps {
  title?: string;
  kind?: string;
  description?: string;
  base_node_name?: string;
  parentNode?: string | null;
  successorNode?: string | null;
  nodeStatus?: string;
  created?: string;
  updated?: string;
  readOnly?: boolean;
  onParameterChanged?: (name: string, value: any) => void;
  executors_info: Record<string, ExecutorInfo>;
  key?: string | number;
}

interface NodePropertiesState {
  title?: string;
  description?: string;
  parentNode?: string | null;
  successorNode?: string | null;
  nodeStatus?: string;
  created?: string;
  readOnly?: boolean;
}

export default class NodeProperties extends Component<NodePropertiesProps, NodePropertiesState> {
  constructor(props: NodePropertiesProps) {
    super(props);
    this.state = {
      title: this.props.title,
      description: this.props.description,
      parentNode: this.props.parentNode,
      successorNode: this.props.successorNode,
      nodeStatus: this.props.nodeStatus,
      created: this.props.created,
      readOnly: this.props.readOnly,
    };
  }

  handleParameterChanged(name: string, value: any) {
    if (this.state.readOnly) {
      return;
    }
    let newValue = value;
    if (name === 'kind' && value && value.values) {
      newValue = value.values[value.index];
    }
    this.setState({ [name]: newValue } as any);
    if (this.props.onParameterChanged) {
      this.props.onParameterChanged(name, newValue);
    }
  }

  render() {
    const customPropertiesItems = [
      {
        name: 'title',
        widget: 'Title',
        value: this.state.title,
        parameter_type: 'str',
        read_only: Boolean(this.state.readOnly),
      },
      {
        name: 'description',
        widget: 'Description',
        value: this.state.description,
        parameter_type: 'str',
        read_only: Boolean(this.state.readOnly),
      },
    ].map((parameter) => (
      <ParameterItem
        name={parameter.name}
        widget={parameter.widget}
        value={parameter.value}
        parameterType={parameter.parameter_type}
        key={parameter.name}
        readOnly={parameter.read_only}
        onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
      />
    ));

    const statePropertiesItems = [
      makeKeyValueRow('Node Status', <i>{this.state.nodeStatus}</i>, 'node_status'),
      makeKeyValueRow('Created', <i>{utcTimeToLocal(this.props.created)}</i>, 'created'),
      makeKeyValueRow('Updated', <i>{utcTimeToLocal(this.props.updated)}</i>, 'updated'),
    ];

    const inheritancePropertiesItems = [
      makeKeyValueRow('Kind', this.props.kind || '', 'kind'),
      makeKeyValueRow(
        'Parent Node',
        this.state.parentNode ? (
          <Link to={`/${COLLECTIONS.TEMPLATES}/${this.state.parentNode}`}>{this.state.parentNode}</Link>
        ) : (
          <i>null</i>
        ),
        'parent_node'
      ),
      makeKeyValueRow(
        'Successor',
        this.props.successorNode ? (
          <Link to={`/${COLLECTIONS.TEMPLATES}/${this.props.successorNode}`}>{this.props.successorNode}</Link>
        ) : (
          <i>null</i>
        ),
        'successor'
      ),
    ];

    return (
      <div className="NodeProperties">
        <div className="PropertyCol">{makePropertiesBox('Properties', customPropertiesItems)}</div>
        <div className="PropertyCol">{makePropertiesBox('State properties', statePropertiesItems)}</div>
        <div className="PropertyCol">{makePropertiesBox('Inheritance', inheritancePropertiesItems)}</div>
      </div>
    );
  }
}
