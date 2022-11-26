/* eslint max-classes-per-file: 0 */
import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Icon from '../Common/Icon';
import {PluginsConsumer} from '../../contexts';

const onDragStart = (event, nodeType) => {
  event.dataTransfer.setData('application/reactflow', nodeType);    // eslint-disable-line no-param-reassign
  event.dataTransfer.effectAllowed = 'move';    // eslint-disable-line no-param-reassign
};

export class HubDraggableEntry extends Component {
  static propTypes = {
    nodeContent: PropTypes.object.isRequired,
  };

  render() {
    const { nodeContent } = this.props;

    return (
      <div
          className="dndnode input"
          onDragStart={(event) => onDragStart(event, JSON.stringify(nodeContent))}
          draggable
        >
        <PluginsConsumer>
        {
            plugins_dict => <div className="hub-item hub-item-node">
              <Icon
                type_descriptor={plugins_dict.executors_info[nodeContent.kind]}
                className="hub-item-icon"
              />
              <div className="hub-item-node-text">
                {nodeContent.title}
              </div>
            </div>
        }
        </PluginsConsumer>
      </div>
    );
  }
}

export class HubResourceTypeBasedEntry extends Component {
  static propTypes = {
    nodeContent: PropTypes.object.isRequired,
    nodeLookupSearch: PropTypes.string.isRequired,
    onClick: PropTypes.func.isRequired
  };

  render() {
    const { nodeContent, nodeLookupSearch, onClick } = this.props;
    const splittedArr = nodeLookupSearch.split(":");
    const inOrOut = splittedArr[0];

    return (
      <div
          className="hub-resource-type-based"
        >
        <PluginsConsumer>
        {
            plugins_dict => <div className="hub-item">
              <div className="hub-item-node">
                  <Icon
                    type_descriptor={plugins_dict.executors_info[nodeContent.kind]}
                    className="hub-item-icon"
                  />
                  <div className="hub-item-node-text">
                    {nodeContent.title}
                  </div>
              </div>
              {
                  inOrOut === "input_file_type" &&
                  nodeContent.inputs.filter(
                      input => input.file_type === splittedArr[1]
                  ).map(
                      input => <div className="hub-item-in-or-out" key={input.name} onClick={() => onClick(nodeContent, input.name)}>
                        &#8627; {input.name}
                        </div>
                  )
              }
              {
                  inOrOut === "output_file_type" &&
                  nodeContent.outputs.filter(
                      output => output.file_type === splittedArr[1]
                  ).map(
                      output => <div className="hub-item-in-or-out" key={output.name} onClick={() => onClick(nodeContent, output.name)}>
                        &#8627; {output.name}
                      </div>
                  )
              }
            </div>
        }
        </PluginsConsumer>
      </div>
    );
  }
}

export function TmpHubEntry(nodeLookupSearch, onClick) {
  return (props) => <HubResourceTypeBasedEntry nodeLookupSearch={nodeLookupSearch} onClick={onClick} {...props}/>;
}
