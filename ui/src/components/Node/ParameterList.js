import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import ParameterItem from './ParameterItem';
import './Parameter.css';

// a little function to help us with reordering the result
const reorder = (list, startIndex, endIndex) => {
  const result = Array.from(list);
  const [removed] = result.splice(startIndex, 1);
  result.splice(endIndex, 0, removed);

  return result;
};

export default class ParameterList extends Component {
  constructor(props) {
    super(props);
    const self = this;
    this.counter = 0;
    props.items.forEach((obj) => {
      obj._key = self.counter.toString();   // eslint-disable-line no-param-reassign
      ++self.counter;
    });
    this.state = {
      items: this.props.items,
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

    this.props.onChanged(items);
  }

  handleChanged(index, name, value) {
    const items = this.state.items;
    items[index][name] = value;
    this.setState({items: items});
    this.props.onChanged(items);
  }

  handleAddItem() {
    const items = this.state.items;

    const name = 'parameter_' + this.counter;
    items.push({
      name: name,
      parameter_type: 'str',
      value: '',
      widget: name,
      mutable_type: true,
      publicable: true,
      removable: true,
      _key: this.counter.toString()
    });

    ++this.counter;

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
      <div className='ParameterList'>
        <DragDropContext onDragEnd={this.onDragEnd}>
          <Droppable droppableId="droppable" isDropDisabled={this.state.readOnly}>
            {(provided, snapshot) => (
              <div className={'ParameterListBackground' + (snapshot.isDraggingOver ? ' ParameterListBackgroundDragging' : '')}
                ref={provided.innerRef}
              >
              {this.state.items.map((item, index) => (
                <Draggable key={item._key} draggableId={item._key} index={index} isDragDisabled={this.state.readOnly}>
                  {(provided, snapshot) => (      // eslint-disable-line no-shadow
                    <div>
                      <div className={'ParameterDiv' + (snapshot.isDragging ? ' ParameterDivDragging' : '')}
                        ref={provided.innerRef}
                        {...provided.draggableProps}
                        {...provided.dragHandleProps}
                      >
                        <ParameterItem
                          name={item.name}
                          parameter_type={item.parameter_type}
                          index={index}
                          value={item.value}
                          widget={item.widget}
                          onChanged={(index, name, value) => this.handleChanged(index, name, value)}    // eslint-disable-line no-shadow
                          onRemove={(index) => this.handleRemoveItem(index)}                            // eslint-disable-line no-shadow
                          readOnly={this.state.readOnly}
                          mutable_type={item.mutable_type}
                          publicable={item.publicable}
                          removable={item.removable}
                        />
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
        {
          !this.state.readOnly &&
          <div
            className={'Add' + (this.state.add_hover ? ' hover' : '')}
            onMouseOver={() => this.setState({add_hover: true})}
            onMouseLeave={() => this.setState({add_hover: false})}
            onClick={() => this.handleAddItem()}
          >
              +
          </div>
        }
      </div>
    );
  }
}

ParameterList.propTypes = {
  items: PropTypes.array,
  readOnly: PropTypes.bool,
  onChanged: PropTypes.func,
};
