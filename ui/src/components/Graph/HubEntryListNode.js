import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { DragSource } from 'react-dnd';
import ItemTypes from '../../DragAndDropsItemTypes';
import Icon from '../Common/Icon';
import {PluginsConsumer} from '../../contexts';


const nodeSource = {
  beginDrag(props) {
    return {
      nodeContent: props.nodeContent,
    };
  },

  endDrag(props, monitor) {
    const item = monitor.getItem();
    const dropResult = monitor.getDropResult();

    if (dropResult) {
      console.log(`You dropped ${item.nodeContent._id} into ${dropResult.name}!`); // eslint-disable-line no-alert
    }
  },
};

class HubEntryListNode extends Component {
  static propTypes = {
    connectDragSource: PropTypes.func.isRequired,
    isDragging: PropTypes.bool.isRequired,
    nodeContent: PropTypes.object.isRequired,
  }

  render() {
    const { connectDragSource } = this.props;
    const { nodeContent } = this.props;

    return connectDragSource(
      <div className={'NodeItemDnD'}>
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

export default DragSource(ItemTypes.NODE_ITEM, nodeSource, (connect, monitor) => ({
  connectDragSource: connect.dragSource(),
  isDragging: monitor.isDragging(),
}))(HubEntryListNode);
