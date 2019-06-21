// src/components/About/index.js
import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { DragSource } from 'react-dnd';
import ItemTypes from '../../DragAndDropsItemTypes';
import NodeItem from '../Common/NodeItem';

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

class NodeListItem extends Component {
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
        <NodeItem
          node={nodeContent}
        />
      </div>
    );
  }
}

export default DragSource(ItemTypes.NODE_ITEM, nodeSource, (connect, monitor) => ({
  connectDragSource: connect.dragSource(),
  isDragging: monitor.isDragging(),
}))(NodeListItem);
