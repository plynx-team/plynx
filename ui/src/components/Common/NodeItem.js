import React, { Component } from 'react';
import {PluginsConsumer} from '../../contexts';
import Icon from './Icon';
import PropTypes from 'prop-types';

import './NodeItem.css';


export default class NodeItem extends Component {
  static propTypes = {
    node: PropTypes.object.isRequired,
  }

  render() {
    const node = this.props.node;
    return <PluginsConsumer>
        {
          plugins_dict => <div className={`NodeItem node-${node._id}`}>
            <div className='node-header'>
              <div className='node-header-title'>
                  <Icon
                    type_descriptor={plugins_dict.executors_info[this.props.node.kind]}
                    className="operation-icon"
                  />
                  <div className="operation-title-text">
                    {plugins_dict.executors_info[this.props.node.kind].title}
                  </div>
              </div>
            </div>
            <div className='NodeDescription'>
              <div className="description-text">
                {node.title}
              </div>
              <div className={node.starred ? 'star-visible' : 'star-hidden'}>
                <img src="/icons/star.svg" alt="star" />
              </div>
            </div>
          </div>
        }
        </PluginsConsumer>;
  }
}
