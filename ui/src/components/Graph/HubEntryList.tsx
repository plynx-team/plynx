import React, { Component, createRef } from 'react';
import Icon from '../Common/Icon';
import './style.css';

export interface HubEntryListProps {
  items: any[];
  hubEntryItem: any;
  extraClassName?: string;
  level?: number;
}

export default class HubEntryList extends Component<HubEntryListProps> {
  static defaultProps = {
    extraClassName: 'open',
    level: 0,
  };

  containerRef = createRef<HTMLDivElement>();

  scrollToTop() {
    if (this.containerRef.current) {
      this.containerRef.current.scrollTop = 0;
    }
  }

  render() {
    const { items, hubEntryItem: HubItemComponent, level = 0, extraClassName = 'open' } = this.props;

    const listItems = items.map((entry) => {
      if (entry._type === 'Group') {
        return (
          <HubEntryListGroup
            key={entry._id}
            hubEntryItem={HubItemComponent}
            group={entry}
            level={level}
          />
        );
      }
      return <HubItemComponent key={entry._id} nodeContent={entry} />;
    });

    return (
      <div className={`hub-entry-list ${extraClassName}`} ref={this.containerRef}>
        {listItems}
      </div>
    );
  }
}

interface HubEntryListGroupProps {
  hubEntryItem: any;
  group: any;
  level: number;
}

interface HubEntryListGroupState {
  open: boolean;
}

class HubEntryListGroup extends Component<HubEntryListGroupProps, HubEntryListGroupState> {
  constructor(props: HubEntryListGroupProps) {
    super(props);
    this.state = {
      open: this.props.level === 0,
    };
  }

  render() {
    const arrowClass = this.state.open ? 'hub-arrow arrow-down' : 'hub-arrow arrow-right';
    return (
      <div className="hub-entry-group noselect">
        <div
          className="hub-item hub-entry-group-title"
          onClick={() => this.setState({ open: !this.state.open })}
        >
          <i className={arrowClass} />
          <Icon
            type_descriptor={{ icon: 'feathericons.folder', color: '#fff' }}
            className="hub-item-icon"
          />
          <div className="hub-entry-group-title-text">{this.props.group.title}</div>
        </div>
        <HubEntryList
          key={this.props.group._id}
          hubEntryItem={this.props.hubEntryItem}
          items={this.props.group.items || []}
          extraClassName={this.state.open ? 'open' : 'closed'}
          level={this.props.level + 1}
        />
      </div>
    );
  }
}
