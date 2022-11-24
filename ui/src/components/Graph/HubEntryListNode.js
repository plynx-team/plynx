import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { DragSource } from 'react-dnd';
import ItemTypes from '../../DragAndDropsItemTypes';
import Icon from '../Common/Icon';
import {PluginsConsumer} from '../../contexts';


const onDragStart = (event, nodeType) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

class HubEntryListNode extends Component {
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

// export default DragSource(ItemTypes.NODE_ITEM, nodeSource, (connect, monitor) => ({
//   connectDragSource: connect.dragSource(),
//   isDragging: monitor.isDragging(),
// }))(HubEntryListNode);
export default HubEntryListNode;
