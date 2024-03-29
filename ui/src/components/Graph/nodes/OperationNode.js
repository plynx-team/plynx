import React, { memo } from 'react';
import PropTypes from 'prop-types';
import { Handle } from 'reactflow';
import {PluginsConsumer} from '../../../contexts';
import Tooltip from '../../Common/Tooltip';
import Icon from '../../Common/Icon';
import ParameterItem from '../../Common/ParameterItem';
import './OperationNode.css';
import { makeControlCheckbox } from '../../Common/controlButton';
import {
  NODE_RUNNING_STATUS, PRIMITIVE_TYPES,
} from '../../../constants';

// TODO: remove the hack with the registry and use built in methods
const nodesRegistry = {};

const PREVIEW_BUTTON = "<div class=preview-button>preview</div>";

const isValidConnection = (connection) => {
  let input;
  let output;
  let ii;

  const sourceNode = nodesRegistry[connection.source].node;
  const targetNode = nodesRegistry[connection.target].node;

  for (ii = 0; ii < sourceNode.outputs.length; ++ii) {
    output = sourceNode.outputs[ii];
    if (output.name === connection.sourceHandle) {
      break;
    }
  }
  for (ii = 0; ii < targetNode.inputs.length; ++ii) {
    input = targetNode.inputs[ii];
    if (input.name === connection.targetHandle) {
      break;
    }
  }
  if (!input.is_array && input.input_references.length > 0) {
    return false;
  }
  return output.file_type === input.file_type;
};

function PrimitiveValue({input, onPrimitiveOverrideChange, editable}) {
  const visible = input.input_references.length === 0;
  if (!visible || !PRIMITIVE_TYPES.hasOwnProperty(input.file_type)) {
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

PrimitiveValue.propTypes = {
  input: PropTypes.shape({
    name: PropTypes.string.isRequired,
    file_type: PropTypes.string.isRequired,
    input_references: PropTypes.array.isRequired,
    primitive_override: PropTypes.any,
  }).isRequired,
  editable: PropTypes.bool.isRequired,
  onPrimitiveOverrideChange: PropTypes.func.isRequired,
};

function InputItem({input, plugins_dict, onPrimitiveOverrideChange, editable}) {
  const type_descriptor = plugins_dict.resources_dict[input.file_type];
  return (
        <div className="flow-node-item flow-node-item-input" key={input.name}>
            <Icon
              type_descriptor={type_descriptor}
            />
            {input.name}
            <PrimitiveValue
              input={input}
              onPrimitiveOverrideChange={onPrimitiveOverrideChange}
              editable={editable}
            />
            <Handle
                type="target"
                position="left"
                id={input.name}
                isValidConnection={isValidConnection}
                style={{width: "11px", height: "11px", left: "-7px", top: "11px"}}
                />
        </div>
  );
}

InputItem.propTypes = {
  input: PropTypes.shape({
    name: PropTypes.string.isRequired,
    file_type: PropTypes.string.isRequired,
    input_references: PropTypes.array,
  }).isRequired,
  plugins_dict: PropTypes.shape({
    resources_dict: PropTypes.object.isRequired,
  }).isRequired,
  editable: PropTypes.bool.isRequired,
  onPrimitiveOverrideChange: PropTypes.func.isRequired,
};

function OutputItem({output, plugins_dict, onOutputClick}) {
  const type_descriptor = plugins_dict.resources_dict[output.file_type];
  return (
        <div className="flow-node-item flow-node-item-output" key={output.name}>
            {output.name}
            <Icon
              type_descriptor={type_descriptor}
            />
            {output.values.length > 0 &&
                <a
                  className="flow-node-item-thumbnail"
                  dangerouslySetInnerHTML={{ __html: output.thumbnail ? output.thumbnail : PREVIEW_BUTTON }}           // eslint-disable-line react/no-danger
                  onClick={() => {
                    onOutputClick(output.name, type_descriptor.display_raw);
                  }}
                />
            }
            <Handle
                type="source"
                position="right"
                id={output.name}
                isValidConnection={isValidConnection}
                style={{width: "11px", height: "11px", right: "-7px", top: "11px"}}
                />
        </div>
  );
}

OutputItem.propTypes = {
  output: PropTypes.shape({
    name: PropTypes.string.isRequired,
    file_type: PropTypes.string.isRequired,
    values: PropTypes.array.isRequired,
    thumbnail: PropTypes.any,
  }).isRequired,
  plugins_dict: PropTypes.shape({
    resources_dict: PropTypes.object.isRequired,
  }).isRequired,
  onOutputClick: PropTypes.func.isRequired,
};

function CustomNode({ id, data }) {
  nodesRegistry[id] = data;
  const node = data.node;

  let node_running_status;
  let outputs;
  if (node._cached_node) {
    node_running_status = node._cached_node.node_running_status.toLowerCase();
    outputs = node._cached_node.outputs;
  } else {
    node_running_status = node.node_running_status.toLowerCase();
    outputs = node.outputs;
  }

  const editable = node._editable === undefined || node._editable;

  return (
      <PluginsConsumer>
      {
        plugins_dict => <div className={`flow-node node-running-status-${node_running_status} node-status-${node.node_status.toLowerCase()} `}>
              <div className="flow-node-header">
                  <Icon
                      type_descriptor={plugins_dict.executors_info[node.kind]}
                      className="flow-node-icon"
                  />
                  <div className="flow-title-text">
                    {node.title}
                  </div>
                  <Tooltip title={node.description} arrow>
                    <div>
                      <Icon
                          type_descriptor={{icon: 'feathericons.help-circle', color: "#aaa"}}
                          className={`flow-title-help ${node.description ? "visible" : "hidden"}`}
                      />
                    </div>
                  </Tooltip>
              </div>
              <div className="flow-node-body">
                  {
                      node.inputs.map(input => <InputItem
                            key={input.name}
                            plugins_dict={plugins_dict}
                            input={input}
                            editable={editable}
                            onPrimitiveOverrideChange={data.onPrimitiveOverrideChange}
                          />
                      )
                  }
                  {
                      outputs.map(output => <OutputItem
                            key={output.name}
                            plugins_dict={plugins_dict}
                            output={output}
                            onOutputClick={data.onOutputClick}
                          />
                      )
                  }
              </div>
              <div className={`flow-node-footer ${node.node_running_status === NODE_RUNNING_STATUS.STATIC || editable ? "visible" : "hidden"}`}>
                {makeControlCheckbox({
                  text: 'Auto run',
                  enabled: node.auto_run_enabled,
                  checked: node.auto_run && node.auto_run_enabled,
                  func: (event) => {
                    event.preventDefault();
                    const target = event.target;
                    const value = target.type === 'checkbox' ? target.checked : target.value;
                    node.auto_run = value;
                  },
                })}
                <Tooltip title="Restart the operation" arrow>
                    <a className="flow-button" onClick={data.onRestartClick}>
                      <Icon
                          type_descriptor={{icon: 'feathericons.refresh-ccw', color: "#aaa"}}
                          className={`flow-button-icon`}
                      />
                    </a>
                  </Tooltip>
              </div>
          </div>
      }
      </PluginsConsumer>
  );
}

CustomNode.propTypes = {
  id: PropTypes.string.isRequired,
  data: PropTypes.shape({
    node: PropTypes.shape({
      _cached_node: PropTypes.shape({
        node_running_status: PropTypes.string.isRequired,
        outputs: PropTypes.array.isRequired,
      }),
      node_running_status: PropTypes.string.isRequired,
      node_status: PropTypes.string.isRequired,
      kind: PropTypes.string.isRequired,
      title: PropTypes.string.isRequired,
      description: PropTypes.string.isRequired,
      auto_run: PropTypes.bool,
      auto_run_enabled: PropTypes.bool,
      inputs: PropTypes.array.isRequired,
      outputs: PropTypes.array.isRequired,
      _editable: PropTypes.bool,
    }).isRequired,
    onOutputClick: PropTypes.func.isRequired,
    onRestartClick: PropTypes.func.isRequired,
    onPrimitiveOverrideChange: PropTypes.func.isRequired,
  }).isRequired,
};

export default memo(CustomNode);
