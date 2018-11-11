// src/components/About/index.js
import React, { Component } from 'react';
import { Link } from 'react-router-dom';
import { PROGRAMMABLE_OPERATIONS } from '../../constants.js';
import './NodeProperties.css'

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

    this.handleChange = this.handleChange.bind(this);
  }

  handleChange(event) {
    if (this.state.readOnly) {
      return;
    }
    var name = event.target.name;
    var value = event.target.value;
    this.setState({[name]: value});
    this.props.onParameterChanged(name, value);
  }

  render() {
    return (
      <div className='NodeProperties'>
        <div className='PropertyCol'>
          <div className='PropertyRow'>
            <div className='PropertyName'>
              Title:
            </div>
            <div className='PropertyValue'>
              <input type="text"
                className='Input'
                name='title'
                value={this.state.title}
                onChange={this.handleChange}
                readOnly={this.state.readOnly}
              />
            </div>
          </div>
          <div className='PropertyRow'>
            <div className='PropertyName'>
              Description:
            </div>
            <div className='PropertyValue'>
              <input type="text"
                className='Input'
                name='description'
                value={this.state.description}
                onChange={this.handleChange}
                readOnly={this.state.readOnly}
              />
            </div>
          </div>
        </div>

        <div className='PropertyCol'>
          <div className='PropertyRow'>
            <div className='PropertyName'>
              Base Node:
            </div>
            <div className='PropertyValue'>
              <select
                className='Select'
                name='base_node_name'
                value={this.state.base_node_name}
                onChange={this.handleChange}
                readOnly={this.state.readOnly}
              >
                {PROGRAMMABLE_OPERATIONS.map((base_node_name) =>
                  <option
                    value={base_node_name}
                    key={base_node_name}
                  >{base_node_name}</option>
                )}
              </select>
            </div>
          </div>

          <div className='PropertyRow'>
            <div className='PropertyName'>
              Node Status:
            </div>
            <div className='PropertyValue'>
              <i>{this.state.nodeStatus}</i>
            </div>
          </div>

        </div>

        <div className='PropertyCol'>
          <div className='PropertyRow'>
            <div className='PropertyName'>
              Parent Node:
            </div>
            <div className='PropertyValue'>
              {this.state.parentNode && <Link to={'/nodes/' + this.state.parentNode}>{this.state.parentNode}</Link> }
              {!this.state.parentNode && <i>null</i> }
            </div>
          </div>

          <div className='PropertyRow'>
            <div className='PropertyName'>
              Successor:
            </div>
            <div className='PropertyValue'>
              {this.props.successorNode && <Link to={'/nodes/' + this.props.successorNode}>{this.props.successorNode}</Link> }
              {!this.props.successorNode && <i>null</i> }
            </div>
          </div>

        </div>

        <div className='PropertyCol'>
          <div className='PropertyRow'>
            <div className='PropertyName'>
              Created:
            </div>
            <div className='PropertyValue'>
              <i>{this.props.created}</i>
            </div>
          </div>

          <div className='PropertyRow'>
            <div className='PropertyName'>
              Updated:
            </div>
            <div className='PropertyValue'>
              <i>{this.props.updated}</i>
            </div>
          </div>

        </div>

      </div>
    );
  }
}
