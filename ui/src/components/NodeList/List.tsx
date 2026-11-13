import React, { Component, ReactNode, createRef } from 'react';
import { listTextElement } from '../Common/ListElements';

export interface HeaderDescriptor {
  title: string;
  tag: string;
}

export interface ListProps {
  header: HeaderDescriptor[];
  items: any[];
  renderItem: (item: any) => ReactNode;
  tag: string;
}

export default class List extends Component<ListProps> {
  containerRef = createRef<HTMLDivElement>();

  scrollToTop() {
    if (this.containerRef.current) {
      this.containerRef.current.scrollTop = 0;
    }
  }

  render() {
    const headerItems = this.props.header.map((headerDescriptor) =>
      listTextElement(`header-item ${headerDescriptor.tag}`.trim(), headerDescriptor.title, headerDescriptor.title)
    );
    const listItems = this.props.items.map((node) => this.props.renderItem(node));

    return (
      <div className="list" ref={this.containerRef}>
        <div className={`${this.props.tag} list-header`}>{headerItems}</div>
        {listItems}
      </div>
    );
  }
}
