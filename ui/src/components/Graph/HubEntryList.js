import React, { Component } from 'react';
import PropTypes from 'prop-types';
import HubEntryListNode from './HubEntryListNode';
import Icon from '../Common/Icon';
import './style.css';


export default class HubEntryList extends Component {
  static propTypes = {
    items: PropTypes.array.isRequired,
    extraClassName: PropTypes.string,
    level: PropTypes.number.isRequired,
  }

  static defaultProps = {
    extraClassName: "open",
    level: 0,
  }

  render() {
    const listItems = this.props.items.map(
      (entry) => {
        if (entry.kind === '_GROUP') {
            return <HubEntryListGroup
                key={entry._id}
                group={entry}
                level={this.props.level}
            />
        } else {
            return <HubEntryListNode
              key={entry._id}
              nodeContent={entry}
              />;
        }
      }
    )

    return (
      <div className={`hub-entry-list ${this.props.extraClassName}`}>
        {listItems}
      </div>
    );
  }
}


class HubEntryListGroup extends Component {
  static propTypes = {
    group: PropTypes.object.isRequired,
    level: PropTypes.number.isRequired,
  }

  constructor(props) {
    super(props);
    this.state = {
      open: this.props.level === 0 ? true : false,
    };
  }

  render() {
    const arrowClass = this.state.open ? "hub-arrow down" : "hub-arrow right";
    return (
      <div className="hub-entry-group noselect">
        <div className="hub-item hub-entry-group-title" onClick={() => this.setState({open: !this.state.open})}>
          <i class={arrowClass}></i>
          <Icon
            type_descriptor={{icon: 'feathericons.folder', color: "#fff"}}
            className="hub-item-icon"
          />
          <div className="hub-entry-group-title-text">
            {this.props.group.title}
          </div>
        </div>
        <HubEntryList
            key={this.props.group._id}
            items={this.props.group.items}
            extraClassName={this.state.open ? "open" : "closed"}
            level={this.props.level + 1}
        />
      </div>
    )
  }
}
