import React, { Component } from 'react';
import PropTypes from 'prop-types';
import SearchBar from '../Common/SearchBar';
import { OPERATIONS } from '../../constants';

export default class NodeBarHeader extends Component {
  static propTypes = {
    selectedTab: PropTypes.oneOf(["operations", "files"]).isRequired,
    search: PropTypes.string.isRequired,
    onUpdateFilter: PropTypes.func.isRequired,
  }

  constructor(props) {
    super(props);
    this.tabName = props.selectedTab;
    this.baseNodeNames = (this.tabName === "operations" ? OPERATIONS : "file");
    this.search = props.search;
    this.initialSearch = props.search;
  }

  onTabClick(e, tabName, baseNodeNames) {
    e.stopPropagation();
    e.preventDefault();
    this.tabName = tabName;
    this.baseNodeNames = baseNodeNames;
    this.searchBar.update(this.initialSearch);
    this.updateFilter();
  }

  handleSearchUpdate(search) {
    this.search = search;
    this.updateFilter();
  }

  updateFilter() {
    this.props.onUpdateFilter(this.tabName, this.baseNodeNames, this.search);
  }

  render() {
    return (
      <div className="NodeBarHeader">
        <div className="menu">
          <div className={"menu-button" + (this.props.selectedTab === "files" ? " selected" : "")}
             onClick={(e) => this.onTabClick(e, "files", "file")}
            >
            {"Files"}
          </div>
          <div className={"menu-button" + (this.props.selectedTab === "operations" ? " selected" : "")}
             onClick={(e) => this.onTabClick(e, "operations", OPERATIONS)}
            >
            {"Operations"}
          </div>
        </div>
        <div className="search">
          <SearchBar
              onSearchUpdate={(search) => this.handleSearchUpdate(search)}
              ref={(child) => {
                this.searchBar = child;
              }}
              search={this.search}
          />
        </div>
      </div>
    );
  }
}
