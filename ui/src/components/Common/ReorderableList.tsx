import React, { Component, ReactNode } from 'react';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';

export function reorder<T>(list: T[], startIndex: number, endIndex: number): T[] {
  const result = Array.from(list);
  const [removed] = result.splice(startIndex, 1);
  result.splice(endIndex, 0, removed);
  return result;
}

export interface ReorderableListProps<T extends { _key?: string }> {
  items: T[];
  readOnly: boolean;
  onChanged: (items: T[]) => void;
  renderItem: (item: T, index: number, isDragging: boolean) => ReactNode;
  droppableId?: string;
  className?: string;
  onAddItem?: () => void;
  addButtonText?: string;
  addButtonClassName?: string;
}

interface ReorderableListState<T> {
  items: T[];
}

export default class ReorderableList<T extends { _key?: string }> extends Component<
  ReorderableListProps<T>,
  ReorderableListState<T>
> {
  counter: number = 0;

  constructor(props: ReorderableListProps<T>) {
    super(props);
    const items = props.items || [];
    items.forEach((obj) => {
      if (!obj._key) {
        obj._key = String(this.counter);
        this.counter += 1;
      }
    });

    this.state = {
      items,
    };

    this.onDragEnd = this.onDragEnd.bind(this);
  }

  componentDidUpdate(prevProps: ReorderableListProps<T>) {
    if (prevProps.items !== this.props.items) {
      const items = this.props.items || [];
      items.forEach((obj) => {
        if (!obj._key) {
          obj._key = String(this.counter);
          this.counter += 1;
        }
      });
      this.setState({ items });
    }
  }

  onDragEnd(result: DropResult) {
    if (!result.destination) {
      return;
    }

    const items = reorder(
      this.state.items,
      result.source.index,
      result.destination.index
    );

    this.setState({ items });
    this.props.onChanged(items);
  }

  render() {
    const { readOnly, droppableId = 'droppable', className = '', renderItem, onAddItem, addButtonText = 'Add', addButtonClassName = 'Add' } = this.props;

    return (
      <div className={className}>
        <DragDropContext onDragEnd={this.onDragEnd}>
          <Droppable droppableId={droppableId} isDropDisabled={readOnly}>
            {(provided) => (
              <div
                ref={provided.innerRef}
                {...provided.droppableProps}
                className="droppable-container"
              >
                {this.state.items.map((item, index) => (
                  <Draggable
                    key={item._key || index}
                    draggableId={String(item._key || index)}
                    index={index}
                    isDragDisabled={readOnly}
                  >
                    {(draggableProvided, snapshot) => (
                      <div
                        ref={draggableProvided.innerRef}
                        {...draggableProvided.draggableProps}
                        {...draggableProvided.dragHandleProps}
                        className="draggable-item"
                      >
                        {renderItem(item, index, snapshot.isDragging)}
                      </div>
                    )}
                  </Draggable>
                ))}
                {provided.placeholder}
              </div>
            )}
          </Droppable>
        </DragDropContext>

        {!readOnly && onAddItem && (
          <div className={addButtonClassName} onClick={onAddItem}>
            <div className="control-button">
              <img src="/icons/plus.svg" alt="add" /> {addButtonText}
            </div>
          </div>
        )}
      </div>
    );
  }
}
