import React, { Component } from 'react';
import PropTypes from 'prop-types';
import HubEntry from './HubEntry';
import Icon from '../Common/Icon';
import {PluginsConsumer} from '../../contexts';
import './HubPanel.css';

export default class HubPanel extends Component {
  constructor(props) {
    super(props);
    this.state = {
      index: 0,
    };
  }

  static propTypes = {
    kind: PropTypes.string.isRequired,
  };

  render() {
    return (
      <PluginsConsumer>
        { plugins_dict => <div className="hub-panel">
            <div className="hub-panel-tab control-toggle">
                {
                    {
                      ...plugins_dict.workflows_dict,
                      ...plugins_dict.operations_dict,
                    }[this.props.kind].hubs.map(hub_kind => plugins_dict.hubs_dict[hub_kind]).map((hub, index) => (
                    <div
                        className={`control-button ${index === this.state.index ? 'selected' : ''}`}
                        onClick={() => {
                          this.setState({index: index});
                        }}
                        key={index}
                    >
                        <Icon
                            type_descriptor={{icon: hub.icon, color: hub.color}}
                            width={15}
                            height={15}
                        />
                        <div className="hub-tab-title">
                            {hub.title}
                        </div>
                    </div>
                ))}
            </div>
            <div className='hub-box-content'>
                <HubEntry
                    hub={{...plugins_dict.workflows_dict, ...plugins_dict.operations_dict}[this.props.kind].hubs[this.state.index]}
                    key={this.state.index}
                />
            </div>

        </div>
        }
      </PluginsConsumer>
    );
  }
}
