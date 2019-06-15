import React, { Component } from 'react';
import PropTypes from 'prop-types';
import OutputItem from './OutputItem';
import ParameterItem from '../Common/ParameterItem';
import makePropertiesBox from '../Common/makePropertiesBox';
import { Link } from 'react-router-dom';
import './style.css';


export default class PropertiesBar extends Component {
  constructor(props) {
    super(props);
    this.state = {
      graphId: props.graphId,
      nodeId: null,
      bigTitle: "Graph",
      parameters: [
        {
          name: 'title',
          parameter_type: "str",
          value: props.graphTitle,
          widget: {
            alias: "Title"
          }
        },
        {
          name: 'description',
          parameter_type: "str",
          value: props.graphDescription,
          widget: {
            alias: "Description"
          }
        }
      ],
      outputs: [],
      logs: [],
      editable: true
    };

    if ('editable' in props) {
      this.state.editable = props.editable;
    }
  }

  // TODO replace it with more general functions
  /* eslint-disable max-params */
  /* eslint-disable no-param-reassign */
  setNodeData(graphId, nodeId, base_node_name, bigTitle, bigDescription, parameters, outputs, logs, parent_node) {
    parameters = parameters.slice(0);
    parameters.unshift({
      name: '_DESCRIPTION',
      widget: {
        alias: 'Description',
      },
      value: bigDescription,
      parameter_type: 'str',
    });
    this.setState(
      {
        graphId: graphId,
        nodeId: nodeId,
        bigTitle: bigTitle,
        parameters: parameters,
        outputs: outputs,
        logs: logs,
        parent_node: parent_node,
        base_node_name: base_node_name
      }
    );
  }
  /* eslint-enable no-param-reassign */
  /* eslint-enable max-params */

  setGraphData(graphId, bigTitle, parameters) {
    this.setState(
      {
        graphId: graphId,
        nodeId: null,
        bigTitle: bigTitle,
        parameters: parameters,
        outputs: [],
        logs: []
      }
    );
  }

  clearData() {
    this.setState({
      nodeId: "",
      title: "",
      parameters: []
    });
  }

  handleParameterChanged(name, value) {
    this.props.onParameterChanged(this.state.nodeId, name, value);
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
          alias={parameter.widget.alias}
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
          key={self.state.nodeId + "$" + output.name}
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
          key={this.state.nodeId + '$' + log.name}
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
          !this.state.nodeId &&
          <div className="PropertiesHeader">{(this.state.bigTitle ? this.state.bigTitle + ' ' : ' ') + 'Properties'}</div>
        }
        {
          (this.state.nodeId && this.state.base_node_name !== 'file') &&
          <Link to={'/nodes/' + this.state.parent_node}>
            <div className="PropertiesHeader">
              {(this.state.bigTitle ? this.state.bigTitle + ' ' : ' ')}<img src="/icons/external-link.svg" width="12" height="12" alt="^" />
            </div>
          </Link>
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
          {!this.state.editable && outputsList.length > 0 && makePropertiesBox('Outputs', outputsList)}
          {!this.state.editable && logsList.length > 0 && makePropertiesBox('Logs', logsList)}
        </div>

      </div>
    );
  }
}

PropertiesBar.propTypes = {
  editable: PropTypes.bool,
  graphDescription: PropTypes.string,
  graphId: PropTypes.string,
  graphTitle: PropTypes.string,
  onFileShow: PropTypes.func,
  onParameterChanged: PropTypes.func,
  onPreview: PropTypes.func,
};
