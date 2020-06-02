import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { NODE_STATUS, COLLECTIONS } from '../../constants';
import ParameterItem from '../Common/ParameterItem';
import makePropertiesBox from '../Common/makePropertiesBox';
import './NodeProperties.css';
import { utcTimeToLocal } from '../../utils';

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
    let newValue = value;
    if (name === 'kind') {
      newValue = value.values[value.index];
    }
    this.setState({[name]: newValue});
    this.props.onParameterChanged(name, newValue);
  }

  render() {
    // Find index of base_node_name
    const kinds = Object.keys(this.props.executors_info);
    const kindIndex = kinds.findIndex(knd => this.props.kind === knd);
    console.log(kinds, kindIndex, this.props.kind);
    const customPropertiesItems = [
      {
        name: 'title',
        widget: 'Title',
        value: this.state.title,
        parameter_type: 'str',
        read_only: this.state.readOnly,
      },
      {
        name: 'description',
        widget: 'Description',
        value: this.state.description,
        parameter_type: 'str',
        read_only: this.state.readOnly,
      },
    ].map(
      (parameter) => <ParameterItem
        name={parameter.name}
        widget={parameter.widget}
        value={parameter.value}
        parameterType={parameter.parameter_type}
        key={parameter.name}
        readOnly={parameter.read_only}
        onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
        />
      );


    const statePropertiesItems = [
      makeKeyValueRow('Node Status', <i>{this.state.nodeStatus}</i>, 'node_status'),
      makeKeyValueRow('Created', <i>{utcTimeToLocal(this.props.created)}</i>, 'created'),
      makeKeyValueRow('Updated', <i>{utcTimeToLocal(this.props.updated)}</i>, 'updated'),
    ];

    const inheritancePropertiesItems = [
      makeKeyValueRow('Kind', this.props.kind, 'kind'),
      makeKeyValueRow(
          'Parent Node',
          this.state.parentNode ? <Link to={`/${COLLECTIONS.TEMPLATES}/${this.state.parentNode}`}>{this.state.parentNode}</Link> : <i>null</i>,
          'parent_node'
        ),
      makeKeyValueRow(
          'Successor',
          this.props.successorNode ? <Link to={`/${COLLECTIONS.TEMPLATES}/${this.state.successorNode}`}>{this.props.successorNode}</Link> : <i>null</i>,
          'successor'
        ),
    ];

    return (
      <div className='NodeProperties'>
        <div className='PropertyCol'>
          { makePropertiesBox('Properties', customPropertiesItems) }
        </div>
        <div className='PropertyCol'>
          { makePropertiesBox('State properties', statePropertiesItems) }
        </div>
        <div className='PropertyCol'>
          { makePropertiesBox('Inheritance', inheritancePropertiesItems) }
        </div>
      </div>

    );
  }
}

NodeProperties.propTypes = {
  title: PropTypes.string,
  kind: PropTypes.string,
  description: PropTypes.string,
  base_node_name: PropTypes.string,
  parentNode: PropTypes.string,
  successorNode: PropTypes.string,
  nodeStatus: PropTypes.oneOf(Object.values(NODE_STATUS)),
  created: PropTypes.string,
  updated: PropTypes.string,
  readOnly: PropTypes.bool,
  onParameterChanged: PropTypes.func,
  executors_info: PropTypes.object.isRequired,      // TODO more detailed
};
