/* eslint max-classes-per-file: 0 */
import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Icon from '../Common/Icon';
import './style.css';


export default class HubEntryList extends Component {
  static propTypes = {
    items: PropTypes.array.isRequired,
    hubEntryItem: PropTypes.func.isRequired,
    extraClassName: PropTypes.string,
    level: PropTypes.number.isRequired,
  };

  static defaultProps = {
    extraClassName: "open",
    level: 0,
  };

  render() {
    const listItems = this.props.items.map(
      (entry) => {
        if (entry._type === 'Group') {
          return <HubEntryListGroup
                key={entry._id}
                hubEntryItem={this.props.hubEntryItem}
                group={entry}
                level={this.props.level}
            />;
        } else {
          return <this.props.hubEntryItem
              key={entry._id}
              nodeContent={entry}
              />;
        }
      }
    );

    return (
      <div className={`hub-entry-list ${this.props.extraClassName}`}>
        {listItems}
      </div>
    );
  }
}

class HubEntryListGroup extends Component {
  static propTypes = {
    hubEntryItem: PropTypes.func.isRequired,
    group: PropTypes.object.isRequired,
    level: PropTypes.number.isRequired,
  };

  constructor(props) {
    super(props);
    this.state = {
      open: this.props.level === 0,
    };
  }

  render() {
    const arrowClass = this.state.open ? "hub-arrow arrow-down" : "hub-arrow arrow-right";
    return (
      <div className="hub-entry-group noselect">
        <div className="hub-item hub-entry-group-title" onClick={() => this.setState({open: !this.state.open})}>
          <i className={arrowClass}></i>
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
            hubEntryItem={this.props.hubEntryItem}
            items={this.props.group.items}
            extraClassName={this.state.open ? "open" : "closed"}
            level={this.props.level + 1}
        />
      </div>
    );
  }
}
