import React, { memo, ChangeEvent, MouseEvent } from 'react';
import { Handle, Connection, NodeProps } from 'reactflow';
import { PluginsConsumer } from '../../../contexts';
import Tooltip from '../../Common/Tooltip';
import Icon from '../../Common/Icon';
import ParameterItem from '../../Common/ParameterItem';
import './OperationNode.css';
import { makeControlCheckbox } from '../../Common/ControlButton';
import { NODE_RUNNING_STATUS, PRIMITIVE_TYPES } from '../../../constants';
import { NodeData, NodeInput, NodeOutput, PluginsDict } from '../../../types';

export const nodesRegistry: Record<string, any> = {};

const PREVIEW_BUTTON = '<div class=preview-button>preview</div>';

export const isValidConnection = (
  connection: Connection,
  registry: Record<string, any> = nodesRegistry
): boolean => {
  if (!connection.source || !connection.target) {
    return false;
  }
  const sourceEntry = registry[connection.source];
  const targetEntry = registry[connection.target];
  if (!sourceEntry || !targetEntry) {
    return false;
  }

  const sourceNode: NodeData = sourceEntry.node;
  const targetNode: NodeData = targetEntry.node;

  const output = (sourceNode.outputs || []).find((out) => out.name === connection.sourceHandle);
  const input = (targetNode.inputs || []).find((inp) => inp.name === connection.targetHandle);

  if (!input || !output) {
    return false;
  }

  if (!input.is_array && input.input_references && input.input_references.length > 0) {
    return false;
  }

  return output.file_type === input.file_type;
};

interface PrimitiveValueProps {
  input: NodeInput;
  editable: boolean;
  onPrimitiveOverrideChange: (name: string, value: any) => void;
}

function PrimitiveValue({ input, onPrimitiveOverrideChange, editable }: PrimitiveValueProps) {
  const visible = !input.input_references || input.input_references.length === 0;
  if (!visible || !Object.prototype.hasOwnProperty.call(PRIMITIVE_TYPES, input.file_type)) {
    return null;
  }
  return (
    <div className="flow-node-primitive-input">
      <ParameterItem
        name={input.name}
        widget={input.name}
        value={input.primitive_override}
        parameterType={input.file_type}
        readOnly={!editable}
        onParameterChanged={(name, value) => {
          onPrimitiveOverrideChange(name, value);
        }}
      />
    </div>
  );
}

interface InputItemProps {
  input: NodeInput;
  plugins_dict: PluginsDict;
  editable: boolean;
  onPrimitiveOverrideChange: (name: string, value: any) => void;
}

function InputItem({ input, plugins_dict, onPrimitiveOverrideChange, editable }: InputItemProps) {
  const typeDescriptor = plugins_dict.resources_dict[input.file_type];
  return (
    <div className="flow-node-item flow-node-item-input" key={input.name}>
      {typeDescriptor && <Icon type_descriptor={typeDescriptor} />}
      {input.name}
      <PrimitiveValue
        input={input}
        onPrimitiveOverrideChange={onPrimitiveOverrideChange}
        editable={editable}
      />
      <Handle
        type="target"
        position={'left' as any}
        id={input.name}
        isValidConnection={isValidConnection}
        style={{ width: '11px', height: '11px', left: '-7px', top: '11px' }}
      />
    </div>
  );
}

interface OutputItemHandleProps {
  output: NodeOutput;
  plugins_dict: PluginsDict;
  onOutputClick: (name: string, displayRaw?: boolean) => void;
}

function OutputItemHandle({ output, plugins_dict, onOutputClick }: OutputItemHandleProps) {
  const typeDescriptor = plugins_dict.resources_dict[output.file_type];
  const displayRaw = typeDescriptor ? typeDescriptor.display_raw : false;
  const values = output.values || [];

  return (
    <div className="flow-node-item flow-node-item-output" key={output.name}>
      {output.name}
      {typeDescriptor && <Icon type_descriptor={typeDescriptor} />}
      {values.length > 0 && (
        <a
          className="flow-node-item-thumbnail"
          dangerouslySetInnerHTML={{ __html: output.thumbnail || PREVIEW_BUTTON }}
          onClick={() => {
            onOutputClick(output.name, displayRaw);
          }}
        />
      )}
      <Handle
        type="source"
        position={'right' as any}
        id={output.name}
        isValidConnection={isValidConnection}
        style={{ width: '11px', height: '11px', right: '-7px', top: '11px' }}
      />
    </div>
  );
}

export interface CustomNodeData {
  node: NodeData;
  onOutputClick: (name: string, displayRaw?: boolean) => void;
  onRestartClick: (e: MouseEvent<any>) => void;
  onPrimitiveOverrideChange: (name: string, value: any) => void;
  [key: string]: any;
}

function CustomNode({ id, data }: NodeProps<CustomNodeData>) {
  nodesRegistry[id] = data;
  const node = data.node;

  let nodeRunningStatus: string;
  let outputs: NodeOutput[];
  if (node._cached_node) {
    nodeRunningStatus = (node._cached_node.node_running_status || 'READY').toLowerCase();
    outputs = node._cached_node.outputs || [];
  } else {
    nodeRunningStatus = (node.node_running_status || 'READY').toLowerCase();
    outputs = node.outputs || [];
  }

  const nodeStatus = (node.node_status || 'READY').toLowerCase();
  const editable = node._editable === undefined || node._editable;

  return (
    <PluginsConsumer>
      {(plugins_dict: PluginsDict) => {
        const executor = plugins_dict.executors_info?.[node.kind];

        return (
          <div
            className={`flow-node node-running-status-${nodeRunningStatus} node-status-${nodeStatus} `}
          >
            <div className="flow-node-header">
              {executor && <Icon type_descriptor={executor} className="flow-node-icon" />}
              <div className="flow-title-text">{node.title}</div>
              <Tooltip title={node.description || ''} arrow>
                <div>
                  <Icon
                    type_descriptor={{ icon: 'feathericons.help-circle', color: '#aaa' }}
                    className={`flow-title-help ${node.description ? 'visible' : 'hidden'}`}
                  />
                </div>
              </Tooltip>
            </div>
            <div className="flow-node-body">
              {(node.inputs || []).map((input) => (
                <InputItem
                  key={input.name}
                  plugins_dict={plugins_dict}
                  input={input}
                  editable={editable}
                  onPrimitiveOverrideChange={data.onPrimitiveOverrideChange}
                />
              ))}
              {outputs.map((output) => (
                <OutputItemHandle
                  key={output.name}
                  plugins_dict={plugins_dict}
                  output={output}
                  onOutputClick={data.onOutputClick}
                />
              ))}
            </div>
            <div
              className={`flow-node-footer ${
                node.node_running_status === NODE_RUNNING_STATUS.STATIC || editable
                  ? 'visible'
                  : 'hidden'
              }`}
            >
              {makeControlCheckbox({
                text: 'Auto run',
                enabled: Boolean(node.auto_run_enabled),
                checked: Boolean(node.auto_run && node.auto_run_enabled),
                func: (event: ChangeEvent<HTMLInputElement>) => {
                  event.preventDefault();
                  const target = event.target;
                  const value = target.type === 'checkbox' ? target.checked : target.value;
                  node.auto_run = value;
                },
              })}
              <Tooltip title="Restart the operation" arrow>
                <a className="flow-button" onClick={data.onRestartClick}>
                  <Icon
                    type_descriptor={{ icon: 'feathericons.refresh-ccw', color: '#aaa' }}
                    className="flow-button-icon"
                  />
                </a>
              </Tooltip>
            </div>
          </div>
        );
      }}
    </PluginsConsumer>
  );
}

export default memo(CustomNode);
