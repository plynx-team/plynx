import React, { memo } from 'react';
import { Handle, useReactFlow, useStoreApi } from 'reactflow';
import {PluginsConsumer} from '../../../contexts';
import Icon from '../../Common/Icon';
import './OperationNode.css';

const options = [
  {
    value: 'smoothstep',
    label: 'Smoothstep',
  },
  {
    value: 'step',
    label: 'Step',
  },
  {
    value: 'default',
    label: 'Bezier (default)',
  },
  {
    value: 'straight',
    label: 'Straight',
  },
];

// TODO: remove the hack with the registry and use built in methods
var nodesRegistry = {};


const isValidConnection = (connection) => {
    var input;
    var output;
    var ii;

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

function InputItem({input, plugins_dict}) {
    const type_descriptor = plugins_dict.resources_dict[input.file_type];
    return (
        <div className="flow-node-item flow-node-item-input" key={input.name}>
            <Icon
              type_descriptor={type_descriptor}
            />
            {input.name}
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
                  dangerouslySetInnerHTML={{ __html: output.thumbnail ? output.thumbnail : "preview" }}           // eslint-disable-line react/no-danger
                  onClick={() => {onOutputClick(output.name, type_descriptor.display_raw)}}
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

  return (
      <PluginsConsumer>
      {
        plugins_dict =>
          <div className={`flow-node node-running-status-${node_running_status} node-status-${node.node_status.toLowerCase()} `}>
              <div className="flow-node-header">
                  <Icon
                      type_descriptor={plugins_dict.executors_info[node.kind]}
                      className="flow-node-icon"
                  />
                  <div className="flow-title-text">
                    {node.title}
                  </div>
              </div>
              <div className="flow-node-body">
                  {
                      node.inputs.map(input =>
                          <InputItem
                            key={input.name}
                            plugins_dict={plugins_dict}
                            input={input}
                          />
                      )
                  }
                  {
                      outputs.map(output =>
                          <OutputItem
                            key={output.name}
                            plugins_dict={plugins_dict}
                            output={output}
                            onOutputClick={data.onOutputClick}
                          />
                      )
                  }
              </div>
          </div>
      }
      </PluginsConsumer>
  );
}

export default memo(CustomNode);
