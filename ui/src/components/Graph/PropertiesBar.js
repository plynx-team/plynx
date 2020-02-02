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

export default class PropertiesBar extends Component {
  constructor(props) {
    super(props);
    this.state = this.getStateDict([props.initialNode]);
  }

  getStateDict(nodes) {
      var commonParameters = JSON.parse(JSON.stringify(nodes.length > 0 ? nodes[0].parameters : []));
      var ii, jj;
      for (ii = 1; ii < nodes.length; ++ii) {
          var indexesToRemove = [];
          for (jj = 0; jj < commonParameters.length; ++jj) {
              let commonParam = commonParameters[jj];
              if (!nodes[ii].parameters.find(param => {
                  return param.name === commonParam.name && param.parameter_type === commonParam.parameter_type && param.value === commonParam.value
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
          });
      }
      if (allEqual(nodes.map(node => node.title))) {
          commonParameters.unshift({
            name: '_TITLE',
            widget: 'title',
            value: nodes[0].title,
            parameter_type: 'str',
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

  handlePreview(previewData) {
    if (this.props.onPreview) {
      this.props.onPreview(previewData);
    }
  }

  render() {
    const self = this;

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
          alias={parameter.widget}
          value={parameter.value}
          parameterType={parameter.parameter_type}
          key={this.state.nodeId + "$" + parameter.name}
          readOnly={!this.state.editable}
          onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
          />);
    }
    const outputsList = this.state.outputs.filter(
      (output) => {
        return output.resource_id !== null;
      }
    ).map(
      (output) => {
        return <OutputItem
          graphId={self.state.graphId}
          resourceName={output.name}
          resourceId={output.resource_id}
          nodeId={self.state.nodeId}
          key={output.resource_id}
          fileType={output.file_type}
          onPreview={(previewData) => self.handlePreview(previewData)}
          />;
      }
      );

    let logsList = [];
    if (this.state.logs) {
      logsList = this.state.logs.filter(
        (log) => {
          return log.resource_id;
        }
        ).map(
        (log) => <OutputItem
          graphId={this.state.graphId}
          resourceName={log.name}
          resourceId={log.resource_id}
          nodeId={this.state.nodeId}
          key={log.resource_id}
          fileType={'file'}
          onPreview={(previewData) => this.handlePreview(previewData)}
        />);
    }

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
                {'Properties of '}
                {renderNodeLink(this.state.nodes[0])}
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
            <div className="PropertiesHeader">
              {(this.state.bigTitle ? this.state.bigTitle + ' ' : ' ')}<img src="/icons/external-link.svg" width="12" height="12" alt="^" />
            </div>
          </div>
        }

        <div className='PropertiesBoxRoot'>
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
