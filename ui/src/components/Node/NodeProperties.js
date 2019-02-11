// src/components/About/index.js
import React, { Component } from 'react';
import { Link } from 'react-router-dom';
import { PROGRAMMABLE_OPERATIONS } from '../../constants.js';
import ParameterItem from '../Common/ParameterItem.js'
import makePropertiesBox from '../Common/makePropertiesBox.js'
import './NodeProperties.css'


function makeKeyValueRow(name, value, key) {
  return (
    <div className='ParameterItem' key={key}>
      <div className='ParameterNameCell'>
        { name }
      </div>
      <div className='ParameterValueCell'>
        { value }
      </div>
    </div>
  );
}

export default class NodeProperties extends Component {
  constructor(props) {
    super(props);
    this.state = {
      title: this.props.title,
      description: this.props.description,
      base_node_name: this.props.base_node_name,
      parentNode: this.props.parentNode,
      nodeStatus: this.props.nodeStatus,
      created: this.props.created,
      readOnly: this.props.readOnly
    };
  }

  handleParameterChanged(name, value) {
    if (this.state.readOnly) {
      return;
    }
    if (name === 'base_node_name') {
      value = value.values[value.index];
    }
    this.setState({[name]: value});
    this.props.onParameterChanged(name, value);
  }

  render() {
    // Find index of base_node_name
    var base_node_index = PROGRAMMABLE_OPERATIONS.indexOf(this.state.base_node_name);
    var base_nodes = null;
    if (base_node_index < 0) {
      base_node_index = 0;
      base_nodes = [this.state.base_node_name];
    } else {
      base_nodes = PROGRAMMABLE_OPERATIONS
    }

    var customPropertiesItems = [
      {
        name: 'title',
        widget: { alias: 'Title' },
        value: this.state.title,
        parameter_type: 'str',
        read_only: this.state.readOnly,
      },
      {
        name: 'description',
        widget: { alias: 'Description' },
        value: this.state.description,
        parameter_type: 'str',
        read_only: this.state.readOnly,
      },
      {
        name: 'base_node_name',
        widget: { alias: 'Base Node' },
        value: {
          index: base_node_index,
          values: base_nodes,
        },
        parameter_type: 'enum',
        read_only: this.state.readOnly,
      },
    ].map(
      (parameter) => <ParameterItem
        name={parameter.name}
        alias={parameter.widget.alias}
        value={parameter.value}
        parameterType={parameter.parameter_type}
        key={parameter.name}
        readOnly={parameter.read_only}
        onParameterChanged={(name, value)=>this.handleParameterChanged(name, value)}
        />
      );

    var internalPropertiesItems = [
        makeKeyValueRow('Node Status', <i>{this.state.nodeStatus}</i>, 'node_status'),
        makeKeyValueRow(
          'Parent Node',
          this.state.parentNode ? <Link to={'/nodes/' + this.state.parentNode}>{this.state.parentNode}</Link> : <i>null</i>,
          'parent_node'
        ),
        makeKeyValueRow(
          'Successor',
          this.props.successorNode ? <Link to={'/nodes/' + this.props.successorNode}>{this.props.successorNode}</Link>: <i>null</i>,
          'successor'
        ),
        makeKeyValueRow('Created', <i>{this.props.created}</i>, 'created'),
        makeKeyValueRow('Updated', <i>{this.props.updated}</i>, 'updated'),
    ];

    return (
      <div className='NodeProperties'>
        <div className='PropertyCol'>
          { makePropertiesBox('Custom properties', customPropertiesItems) }
        </div>
        <div className='PropertyCol'>
          { makePropertiesBox('Internal properties', internalPropertiesItems) }
        </div>
      </div>

    );
  }
}
