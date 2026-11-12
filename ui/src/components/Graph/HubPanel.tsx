import React, { Component } from 'react';
import HubEntry from './HubEntry';
import Icon from '../Common/Icon';
import { PluginsConsumer } from '../../contexts';
import { PluginsDict } from '../../types';
import './HubPanel.css';

export interface HubPanelProps {
  kind: string;
  hubEntryItem: any;
  hiddenSearch?: string;
}

interface HubPanelState {
  index: number;
}

export default class HubPanel extends Component<HubPanelProps, HubPanelState> {
  constructor(props: HubPanelProps) {
    super(props);
    this.state = {
      index: 0,
    };
  }

  render() {
    return (
      <PluginsConsumer>
        {(plugins_dict: PluginsDict) => {
          const allDict = {
            ...((plugins_dict as any).workflows_dict || {}),
            ...(plugins_dict.operations_dict || {}),
          };
          const kindObj = allDict[this.props.kind] || { hubs: [] };
          const hubsList = kindObj.hubs || [];
          const hubsDict = plugins_dict.hubs_dict || {};
          const currentHubKind = hubsList[this.state.index];

          return (
            <div className="hub-panel">
              <div className="hub-panel-tab control-toggle">
                {hubsList
                  .map((hubKind: string) => hubsDict[hubKind])
                  .filter(Boolean)
                  .map((hub: any, index: number) => (
                    <div
                      className={`control-button ${index === this.state.index ? 'selected' : ''}`}
                      onClick={() => {
                        this.setState({ index });
                      }}
                      key={index}
                    >
                      <Icon
                        type_descriptor={{ icon: hub.icon, color: hub.color }}
                        width={15}
                        height={15}
                      />
                      <div className="hub-tab-title">{hub.title}</div>
                    </div>
                  ))}
              </div>
              <div className="hub-box-content">
                {currentHubKind && (
                  <HubEntry
                    hub={currentHubKind}
                    key={this.state.index}
                    hubEntryItem={this.props.hubEntryItem}
                    hiddenSearch={this.props.hiddenSearch}
                  />
                )}
              </div>
            </div>
          );
        }}
      </PluginsConsumer>
    );
  }
}
