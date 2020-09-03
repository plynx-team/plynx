import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import InOutItem from './InOutItem';
import './InOut.css';

// a little function to help us with reordering the result
const reorder = (list, startIndex, endIndex) => {
  const result = Array.from(list);
  const [removed] = result.splice(startIndex, 1);
  result.splice(endIndex, 0, removed);

  return result;
};

export default class InOutList extends Component {
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

    items.push({
      name: 'file_' + this.counter,
      file_type: 'file',
      values: [],
      min_count: 1,
      is_array: false,
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

  handlePreview(previewData) {
    this.props.onPreview(previewData);
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
                <Draggable key={item._key} draggableId={item._key} index={index} isDragDisabled={this.state.readOnly}>
                  {(provided, snapshot) => (      // eslint-disable-line no-shadow
                    <div>
                      <div className={'InOutDiv' + (snapshot.isDragging ? ' InOutDivDragging' : '')}
                        ref={provided.innerRef}
                        {...provided.draggableProps}
                        {...provided.dragHandleProps}
                      >
                        {
                          this.props.varName === 'inputs' &&
                          <InOutItem
                            item={item}
                            index={index}
                            varName={this.props.varName}
                            onChanged={(index, name, value) => this.handleChanged(index, name, value)}  // eslint-disable-line no-shadow
                            onRemove={(index) => this.handleRemoveItem(index)}                          // eslint-disable-line no-shadow
                            readOnly={this.state.readOnly}
                            nodeKind={this.props.nodeKind}
                            onPreview={(previewData) => this.handlePreview(previewData)}
                          />
                        }
                        {
                          this.props.varName === 'outputs' &&
                          <InOutItem
                            item={item}
                            index={index}
                            varName={this.props.varName}
                            onChanged={(index, name, value) => this.handleChanged(index, name, value)}  // eslint-disable-line no-shadow
                            onRemove={(index) => this.handleRemoveItem(index)}                          // eslint-disable-line no-shadow
                            readOnly={this.state.readOnly}
                            nodeKind={this.props.nodeKind}
                            onPreview={(previewData) => this.handlePreview(previewData)}
                          />
                        }
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

InOutList.propTypes = {
  varName: PropTypes.string,
  nodeKind: PropTypes.string,
  items: PropTypes.array,
  readOnly: PropTypes.bool,
  onChanged: PropTypes.func,
  onPreview: PropTypes.func.isRequired,
};
