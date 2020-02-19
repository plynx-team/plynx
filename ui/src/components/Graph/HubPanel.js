import React, { Component } from 'react';
import PropTypes from 'prop-types';
import HubEntry from './HubEntry';
import Icon from '../Common/Icon';
import {PluginsConsumer} from '../../contexts';
import './HubPanel.css';


class HubItem extends Component {
    constructor(props) {
      super(props);
      this.state = {
          open: true,
      }
    }

    render() {
        return (
        <div className='hub-box'>
            <div className='hub-box-header' onClick={() => this.setState({open: !this.state.open})}>
                <i class={`arrow ${this.state.open ? 'down' : 'right' }`}></i>{this.props.hub.title}
            </div>
            { this.state.open &&
            <div className='hub-box-content'>
                <HubEntry/>
            </div>
            }
        </div>
        );
    }
}


export default class HubPanel extends Component {
  constructor(props) {
    super(props);
    this.state = {
      index: 0,
    }
  }
  render() {
    return (
      <PluginsConsumer>
        { plugins_dict =>
        <div className="hub-panel">
            <div className="hub-panel-tab control-toggle">
                {Object.values(plugins_dict.hubs_dict).map((hub, index) => (
                    <div
                        className={`control-button ${index === this.state.index ? 'selected': ''}`}
                        onClick={() => {this.setState({index: index})}}
                        key={index}
                    >
                        <Icon
                            type_descriptor={{icon: hub.icon, color:"#fff"}}
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
                    hub={Object.values(plugins_dict.hubs_dict)[this.state.index].kind}
                    key={this.state.index}
                />
            </div>


        </div>
        }
      </PluginsConsumer>
    );
    //Object.values(plugins_dict.hubs_dict).map(hub => <HubItem hub={hub}/>)
  }
}
