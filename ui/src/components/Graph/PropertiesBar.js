import React, { Component } from 'react';
import PropTypes from 'prop-types';
import OutputItem from './OutputItem';
import ParameterItem from '../Common/ParameterItem';
import makePropertiesBox from '../Common/makePropertiesBox';
import { COLLECTIONS } from '../../constants';
import { Link } from 'react-router-dom';
import './style.css';


const allEqual = arr => arr.every( v => v === arr[0] )


const renderNodeLink = node => {
    let node_id = node.original_node_id || node.parent_node_id;
    if (node_id) {
        return <Link to={`/${COLLECTIONS.TEMPLATES}/${node.original_node_id || node.parent_node_id}`}>
          {node.title}
        </Link>;
    }
    return node.title;
}

const renderLinkRow = (title, href, text) => {
  return (
    <div className='ParameterItem'
      key={href + text}>
      <div className='ParameterNameCell'>
          {title}
      </div>
      <div className='ParameterValueCell'>
        <a href={href}>
          {text}
        </a>
      </div>
    </div>
  );
}

export default class PropertiesBar extends Component {
  constructor(props) {
    super(props);
    this.state = this.getStateDict([props.initialNode]);
    this.mainNodeId = props.initialNode._id;
  }

  getStateDict(nodes) {
      var commonParameters = JSON.parse(JSON.stringify(nodes.length > 0 ? nodes[0].parameters : []));
      var ii, jj;
      for (ii = 1; ii < nodes.length; ++ii) {
          var indexesToRemove = [];
          for (jj = 0; jj < commonParameters.length; ++jj) {
              let commonParam = commonParameters[jj];
              if (!nodes[ii].parameters.find(param => {
                  return param.name === commonParam.name && param.parameter_type === commonParam.parameter_type &&
                    (
                        (param.reference === null && param.value === commonParam.value) ||
                        (param.reference && param.reference === commonParam.reference)
                    )
                  })
              ) {
                  indexesToRemove.push(jj);
              }
          }
          while(indexesToRemove.length) {
              commonParameters.splice(indexesToRemove.pop(), 1);
          }
      }
      if (allEqual(nodes.map(node => node.description))) {
          commonParameters.unshift({
            name: '_DESCRIPTION',
            widget: 'Description',
            value: nodes[0].description,
            parameter_type: 'str',
            _link_visibility: false,
          });
      }
      if (allEqual(nodes.map(node => node.title))) {
          commonParameters.unshift({
            name: '_TITLE',
            widget: 'title',
            value: nodes[0].title,
            parameter_type: 'str',
            _link_visibility: false,
          });
      }
      return {
          nodes: nodes,
          parameters: commonParameters,
          outputs: nodes.map(node => node.outputs).flat(1),
          logs: nodes.map(node => node.logs).flat(1),
          nodeId: nodes.map(node => node._id).join(),
          editable: this.props.editable,
      };
  }

  // TODO replace it with more general functions
  /* eslint-disable max-params */
  /* eslint-disable no-param-reassign */
  setNodeData(node) {
    this.setNodeDataArr([node]);
  }

  setNodeDataArr(nodes) {
    this.setState(this.getStateDict(nodes))
  }
  /* eslint-enable no-param-reassign */
  /* eslint-enable max-params */


  handleParameterChanged(name, value) {
    this.props.onParameterChanged(this.state.nodes.map(node => node._id), name, value);
  }

  handleLinkClick(name) {
    this.props.onLinkClick(this.state.nodes.map(node => node._id), name);
  }

  handlePreview(previewData) {
    if (this.props.onPreview) {
      this.props.onPreview(previewData);
    }
  }

  renderOutputs(outputs) {
      return outputs.filter(
        (output) => {
          return output.values.length > 0;
        }
      ).map(
        (output) => output.values.map(
            (output_value) => {
              return <OutputItem
                graphId={this.state.graphId}
                resourceName={output.name}
                resourceId={output_value}
                nodeId={this.state.nodeId}
                key={output_value}
                fileType={output.file_type}
                onPreview={(previewData) => this.handlePreview(previewData)}
                />;
            }
        )
      );
  }

  render() {
    const self = this;

    let linksList = [];
    if (this.state.nodes.length === 1) {
        const node = this.state.nodes[0];
        const node_id = node.original_node_id || node.parent_node_id;
        if (node_id) {
            linksList.push(renderLinkRow('Original', `/${COLLECTIONS.TEMPLATES}/${node_id}`, node_id));
        }
        var url = window.location.href;
        if (url.indexOf('?') > -1){
           url += '&'
        }else{
           url += '?'
        }
        if (node_id) {
            linksList.push(renderLinkRow('This Operation', `${url}sub_node_id=${node._id}`, node._id));
        }
    }

    let parametersList = [];
    if (this.state.parameters) {
      parametersList = this.state.parameters.filter(
        (parameter) => {
          return parameter.widget !== null;
        }
      )
      .map(
        (parameter) => <ParameterItem
          name={parameter.name}
          widget={parameter.widget}
          value={parameter.value}
          parameterType={parameter.parameter_type}
          key={this.state.nodeId + "$" + parameter.name + parameter.reference}
          readOnly={!this.state.editable}
          _link_visibility={parameter.hasOwnProperty('_link_visibility') ? parameter._link_visibility : (self.mainNodeId === this.state.nodes[0]._id ? false : true)}
          reference={parameter.reference}
          onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
          onLinkClick={(name) => this.handleLinkClick(name)}
          />);
    }
    const outputsList = this.renderOutputs(this.state.outputs);
    const logsList = this.renderOutputs(this.state.logs);

    return (
      <div className="PropertiesBar"
        onClick={(e) => {
          e.stopPropagation();
        }}
        onMouseDown={(e) => {
          e.stopPropagation();
        }}
        >
        {
            this.state.nodes.length > 1 &&
            <div className="PropertiesHeader">
                {'Properties of ' + this.state.nodes.length + ' nodes'}
            </div>
        }
        {
            this.state.nodes.length === 1 &&
            <div className="PropertiesHeader">
                {`Properties of ${this.state.nodes[0].title}`}
            </div>
        }
        {
          (this.state.nodeId && this.state.base_node_name === 'file') &&
          <div onClick={
            (e) => {
              e.stopPropagation();
              e.preventDefault();
              this.props.onFileShow(this.state.nodeId);
            }
          }>
          </div>
        }

        <div className='PropertiesBoxRoot'>
          {linksList.length > 0 && makePropertiesBox('Links', linksList)}
          {parametersList.length > 0 && makePropertiesBox('Parameters', parametersList)}
          {outputsList.length > 0 && makePropertiesBox('Outputs', outputsList)}
          {logsList.length > 0 && makePropertiesBox('Logs', logsList)}
        </div>

      </div>
    );
  }
}

PropertiesBar.propTypes = {
  editable: PropTypes.bool,
  initialNode: PropTypes.object,
  onFileShow: PropTypes.func,
  onParameterChanged: PropTypes.func,
  onPreview: PropTypes.func,
};
