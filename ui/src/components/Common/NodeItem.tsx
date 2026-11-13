import React, { Component } from 'react';
import { PluginsConsumer } from '../../contexts';
import Icon from './Icon';
import { NodeData, PluginsDict } from '../../types';
import './NodeItem.css';

export interface NodeItemProps {
  node: NodeData;
}

export default class NodeItem extends Component<NodeItemProps> {
  render() {
    const { node } = this.props;
    return (
      <PluginsConsumer>
        {(plugins_dict: PluginsDict) => {
          const executorInfo = plugins_dict.executors_info && plugins_dict.executors_info[node.kind];
          return (
            <div className={`NodeItem node-${node._id}`}>
              <div className="node-header">
                <div className="node-header-title">
                  {executorInfo && (
                    <Icon
                      type_descriptor={executorInfo}
                      className="operation-icon"
                    />
                  )}
                  <div className="operation-title-text">
                    {executorInfo ? executorInfo.title : node.kind}
                  </div>
                </div>
              </div>
              <div className="NodeDescription">
                <div className="description-text">{node.title}</div>
                <div className={node.starred ? 'star-visible' : 'star-hidden'}>
                  <img src="/icons/star.svg" alt="star" />
                </div>
              </div>
            </div>
          );
        }}
      </PluginsConsumer>
    );
  }
}
