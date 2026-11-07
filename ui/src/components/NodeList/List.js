import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { listTextElement } from '../Common/listElements';

export default class List extends Component {
  static propTypes = {
    header: PropTypes.array.isRequired,
    items: PropTypes.array.isRequired,
    renderItem: PropTypes.func.isRequired,
    tag: PropTypes.string.isRequired,
  };

  containerRef = React.createRef();

  scrollToTop() {
    if (this.containerRef.current) {
      this.containerRef.current.scrollTop = 0;
    }
  }

  render() {
    const headerItems = this.props.header.map(
        (headerDescriptor) => listTextElement('header-item ' + headerDescriptor.tag, headerDescriptor.title, headerDescriptor.title)
    );
    const listItems = this.props.items.map(
      (node) => this.props.renderItem(node)
    );

    return (
      <div className='list' ref={this.containerRef}>
        <div className={this.props.tag + ' list-header'}>
          {headerItems}
        </div>
        {listItems}
      </div>
    );
  }
}
