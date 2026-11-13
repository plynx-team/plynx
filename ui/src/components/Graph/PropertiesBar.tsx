import React, { Component } from 'react';
import cookie from '../../cookie';
import OutputItem from './OutputItem';
import ParameterItem from '../Common/ParameterItem';
import makePropertiesBox from '../Common/PropertiesBox';
import { COLLECTIONS, IAM_POLICIES } from '../../constants';
import { NodeData, NodeOutput, NodeParameter, PreviewData } from '../../types';
import './style.css';

const allEqual = (arr: any[]) => arr.every((v) => v === arr[0]);

const renderLinkRow = (title: string, href: string, text: string) => (
  <div className="ParameterItem" key={href + text}>
    <div className="ParameterNameCell">{title}</div>
    <div className="ParameterValueCell">
      <a href={href}>{text}</a>
    </div>
  </div>
);

export interface PropertiesBarProps {
  className?: string;
  editable?: boolean;
  initialNode: NodeData;
  onFileShow?: (nodeId: string) => void;
  onParameterChanged: (nodeIds: string[], name: string, value: any) => void;
  onPreview?: (previewData: PreviewData) => void;
  onLinkClick: (nodeIds: string[], name: string) => void;
}

interface PropertiesBarState {
  nodes: NodeData[];
  parameters: NodeParameter[];
  outputs: NodeOutput[];
  logs: any[];
  nodeId: string;
  editable?: boolean;
  base_node_name?: string;
}

export default class PropertiesBar extends Component<PropertiesBarProps, PropertiesBarState> {
  canViewOperations: boolean;
  mainNodeId: string;

  constructor(props: PropertiesBarProps) {
    super(props);

    const user = cookie.load('user');
    const policies = (user && user.policies) || [];
    this.canViewOperations = policies.includes(IAM_POLICIES.CAN_VIEW_OPERATIONS);

    this.state = this.getStateDict([props.initialNode]);
    this.mainNodeId = props.initialNode._id;
  }

  getStateDict(nodes: NodeData[]): PropertiesBarState {
    const commonParameters: NodeParameter[] = JSON.parse(
      JSON.stringify(nodes.length > 0 ? nodes[0].parameters || [] : [])
    );

    for (let ii = 1; ii < nodes.length; ++ii) {
      const indexesToRemove: number[] = [];
      for (let jj = 0; jj < commonParameters.length; ++jj) {
        const commonParam = commonParameters[jj];
        const found = (nodes[ii].parameters || []).find(
          (param) =>
            param.name === commonParam.name &&
            param.parameter_type === commonParam.parameter_type &&
            ((param.reference === null && param.value === commonParam.value) ||
              (param.reference && param.reference === commonParam.reference))
        );
        if (!found) {
          indexesToRemove.push(jj);
        }
      }
      while (indexesToRemove.length) {
        commonParameters.splice(indexesToRemove.pop()!, 1);
      }
    }

    if (nodes.length > 0 && allEqual(nodes.map((node) => node.title))) {
      commonParameters.unshift({
        name: '_TITLE',
        widget: 'title',
        value: nodes[0].title,
        parameter_type: 'str',
        _link_visibility: false,
      });
    }

    const overridenOutputs = nodes
      .filter((node) => Boolean(node._cached_node))
      .map((node) => node._cached_node!.outputs || [])
      .flat(1);
    const overridenLogs = nodes
      .filter((node) => Boolean(node._cached_node))
      .map((node) => node._cached_node!.logs || [])
      .flat(1);

    return {
      nodes,
      parameters: commonParameters,
      outputs:
        overridenOutputs.length !== 0
          ? overridenOutputs
          : nodes.map((node) => node.outputs || []).flat(1),
      logs:
        overridenLogs.length !== 0
          ? overridenLogs
          : nodes.map((node) => node.logs || []).flat(1),
      nodeId: nodes.map((node) => node._id).join(),
      editable: this.props.editable,
    };
  }

  setNodeData(node: NodeData) {
    this.setNodeDataArr([node]);
  }

  setNodeDataArr(nodes: NodeData[]) {
    this.setState(this.getStateDict(nodes));
  }

  handleParameterChanged(name: string, value: any) {
    this.props.onParameterChanged(
      this.state.nodes.map((node) => node._id),
      name,
      value
    );
  }

  handleLinkClick(name: string) {
    this.props.onLinkClick(
      this.state.nodes.map((node) => node._id),
      name
    );
  }

  handlePreview(previewData: PreviewData) {
    if (this.props.onPreview) {
      this.props.onPreview(previewData);
    }
  }

  renderOutputs(outputs: NodeOutput[]) {
    return outputs
      .filter((output) => output.values && output.values.length > 0)
      .map((output) =>
        output.values.map((output_value: any) => (
          <OutputItem
            item={output}
            key={output_value}
            onPreview={(previewData) => this.handlePreview(previewData)}
          />
        ))
      );
  }

  render() {
    const linksList: React.ReactNode[] = [];
    if (this.state.nodes.length === 1 && this.canViewOperations) {
      const node = this.state.nodes[0];
      const nodeId = node.original_node_id || node.parent_node_id;
      if (nodeId) {
        linksList.push(renderLinkRow('Original', `/${COLLECTIONS.TEMPLATES}/${nodeId}`, nodeId));
      }
      let url = window.location.href;
      if (url.includes('?')) {
        url += '&';
      } else {
        url += '?';
      }
      if (nodeId) {
        linksList.push(renderLinkRow('This Operation', `${url}sub_node_id=${node._id}`, node._id));
      }
    }

    let parametersList: React.ReactNode[] = [];
    if (this.state.parameters) {
      parametersList = this.state.parameters
        .filter((parameter) => parameter.widget !== null && parameter.widget !== undefined)
        .map((parameter) => (
          <ParameterItem
            name={parameter.name}
            widget={parameter.widget || parameter.name}
            value={parameter.value}
            parameterType={parameter.parameter_type}
            key={`${this.state.nodeId}$${parameter.name}${parameter.reference}`}
            readOnly={!this.state.editable}
            _link_visibility={
              Object.prototype.hasOwnProperty.call(parameter, '_link_visibility')
                ? parameter._link_visibility
                : this.mainNodeId !== this.state.nodes[0]._id
            }
            reference={parameter.reference}
            onParameterChanged={(name, value) => this.handleParameterChanged(name, value)}
            onLinkClick={(name) => this.handleLinkClick(name)}
          />
        ));
    }
    const outputsList = this.renderOutputs(this.state.outputs);
    const logsList = this.renderOutputs(this.state.logs);

    return (
      <div
        className="PropertiesBar"
        onClick={(e) => {
          e.stopPropagation();
        }}
        onMouseDown={(e) => {
          e.stopPropagation();
        }}
      >
        {this.state.nodes.length > 1 && (
          <div className="PropertiesHeader">{`Properties of ${this.state.nodes.length} nodes`}</div>
        )}
        {this.state.nodes.length === 1 && (
          <div className="PropertiesHeader">{`Properties of ${this.state.nodes[0].title}`}</div>
        )}

        <div className="PropertiesBoxRoot">
          {linksList.length > 0 && makePropertiesBox('Links', linksList)}
          {parametersList.length > 0 && makePropertiesBox('Parameters', parametersList)}
          {outputsList.length > 0 && makePropertiesBox('Outputs', outputsList)}
          {logsList.length > 0 && makePropertiesBox('Logs', logsList)}
        </div>
      </div>
    );
  }
}
