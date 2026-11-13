import React, { Component, DragEvent } from 'react';
import Tooltip from '../Common/Tooltip';
import Icon from '../Common/Icon';
import { PluginsConsumer } from '../../contexts';
import { NodeData, PluginsDict } from '../../types';

const onDragStart = (event: DragEvent<HTMLDivElement>, nodeType: string) => {
  event.dataTransfer.setData('application/reactflow', nodeType);
  event.dataTransfer.effectAllowed = 'move';
};

export interface HubDraggableEntryProps {
  nodeContent: NodeData;
}

export class HubDraggableEntry extends Component<HubDraggableEntryProps> {
  render() {
    const { nodeContent } = this.props;

    return (
      <div
        className="dndnode input"
        onDragStart={(event) => onDragStart(event, JSON.stringify(nodeContent))}
        draggable
      >
        <PluginsConsumer>
          {(plugins_dict: PluginsDict) => {
            const executor = plugins_dict.executors_info?.[nodeContent.kind];
            return (
              <div className="hub-item hub-item-node">
                {executor && <Icon type_descriptor={executor} className="hub-item-icon" />}
                <div className="hub-item-node-text">{nodeContent.title}</div>
                <Tooltip title={nodeContent.description || ''} arrow>
                  <div className="hub-item-help-wrapper">
                    <Icon
                      type_descriptor={{ icon: 'feathericons.help-circle', color: '#aaa' }}
                      className={`hub-item-help ${nodeContent.description ? 'visible' : 'hidden'}`}
                    />
                  </div>
                </Tooltip>
              </div>
            );
          }}
        </PluginsConsumer>
      </div>
    );
  }
}

export interface HandlerHubResourceTypeBasedEntryProps {
  nodeContent: NodeData;
  nodeLookupSearch: string;
  onClick: (nodeContent: NodeData, name: string) => void;
}

export class HandlerHubResourceTypeBasedEntry extends Component<HandlerHubResourceTypeBasedEntryProps> {
  render() {
    const { nodeContent, nodeLookupSearch, onClick } = this.props;
    const splittedArr = nodeLookupSearch.split(':');
    const inOrOut = splittedArr[0];

    return (
      <div className="hub-resource-type-based">
        <PluginsConsumer>
          {(plugins_dict: PluginsDict) => {
            const executor = plugins_dict.executors_info?.[nodeContent.kind];
            return (
              <div className="hub-item">
                <div className="hub-item-node">
                  {executor && <Icon type_descriptor={executor} className="hub-item-icon" />}
                  <div className="hub-item-node-text">{nodeContent.title}</div>
                  <Tooltip title={nodeContent.description || ''} arrow style={{ zIndex: 30000 }}>
                    <div>
                      <Icon
                        type_descriptor={{ icon: 'feathericons.help-circle', color: '#aaa' }}
                        className="hub-item-help hidden"
                      />
                    </div>
                  </Tooltip>
                </div>
                {inOrOut === 'input_file_type' &&
                  (nodeContent.inputs || [])
                    .filter((input) => input.file_type === splittedArr[1])
                    .map((input) => (
                      <div
                        className="hub-item-in-or-out"
                        key={input.name}
                        onClick={() => onClick(nodeContent, input.name)}
                      >
                        &#8627; {input.name}
                      </div>
                    ))}
                {inOrOut === 'output_file_type' &&
                  (nodeContent.outputs || [])
                    .filter((output) => output.file_type === splittedArr[1])
                    .map((output) => (
                      <div
                        className="hub-item-in-or-out"
                        key={output.name}
                        onClick={() => onClick(nodeContent, output.name)}
                      >
                        &#8627; {output.name}
                      </div>
                    ))}
              </div>
            );
          }}
        </PluginsConsumer>
      </div>
    );
  }
}

export function HubResourceTypeBasedEntry(
  nodeLookupSearch: string,
  onClick: (nodeContent: NodeData, name: string) => void
) {
  return (props: any) => (
    <HandlerHubResourceTypeBasedEntry
      nodeLookupSearch={nodeLookupSearch}
      onClick={onClick}
      {...props}
    />
  );
}
