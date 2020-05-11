import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';


// a little function to help us with reordering the result
const reorder = (list, startIndex, endIndex) => {
  const result = Array.from(list);
  const [removed] = result.splice(startIndex, 1);
  result.splice(endIndex, 0, removed);

  return result;
};

export default class DirectoryColumn extends Component {
  constructor(props) {
    super(props);
    const self = this;
    this.counter = 0;
    props.items.forEach((obj) => {
      obj._key = self.counter.toString();   // eslint-disable-line no-param-reassign
      ++self.counter;
    });
    this.state = {
      items: props.items,
      readOnly: this.props.readOnly
    };
    this.onDragEnd = this.onDragEnd.bind(this);
  }

  onDragEnd(result) {
    // dropped outside the list
    if (!result.destination) {
      return;
    }

    const items = reorder(
      this.state.items,
      result.source.index,
      result.destination.index
    );

    this.setState({
      items,
    });
    //this.props.onChanged(items);
  }

  handleChanged(index, name, value) {
    const items = this.state.items;
    items[index][name] = value;
    this.setState({items: items});
    this.props.onChanged(items);
  }

  handleRemoveItem(index) {
    const items = this.state.items;
    items.splice(index, 1);
    this.setState({items: items});
    this.props.onChanged(items);
  }

  // Normally you would want to split things out into separate components.
  // But in this example everything is just done in one place for simplicity
  render() {
    return (
      <div className='InOutList'>
        <DragDropContext onDragEnd={this.onDragEnd}>
          <Droppable droppableId="droppable" isDropDisabled={this.state.readOnly}>
            {(provided, snapshot) => (
              <div className={'InOutListBackground' + (snapshot.isDraggingOver ? ' InOutListBackgroundDragging' : '')}
                ref={provided.innerRef}
              >
              {this.state.items.map((item, index) => (
                <Draggable key={item._id} draggableId={item._id} index={index} isDragDisabled={false}>
                  {(provided, snapshot) => (      // eslint-disable-line no-shadow
                    <div>
                      <div className={'InOutDiv' + (snapshot.isDragging ? ' InOutDivDragging' : '')}
                        ref={provided.innerRef}
                        {...provided.draggableProps}
                        {...provided.dragHandleProps}
                      >
                          <div className="drag-class">
                          {item.title}
                          </div>
                      </div>
                      {provided.placeholder}
                    </div>
                  )}
                </Draggable>
              ))}
              {provided.placeholder}
            </div>
          )}
          </Droppable>
        </DragDropContext>
      </div>
    );
  }
}
