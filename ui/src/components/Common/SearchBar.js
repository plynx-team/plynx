import React, { Component } from 'react';
import PropTypes from 'prop-types';
import './SearchBar.css';

const WAIT_INTERVAL = 400;

export default class SearchBar extends Component {
  static propTypes = {
    search: PropTypes.string.isRequired,
    onSearchUpdate: PropTypes.func.isRequired,
  }

  constructor(props) {
    super(props);
    this.search = this.props.search || '';
    this.state = {
      search: this.search
    };
    this.timer = null;
  }

  handleInputChange(event) {
    clearTimeout(this.timer);

    const value = event.target.value;
    this.searchUpdate(value);

    // If the new value is '', update search right away
    if (value === '') {
      this.triggerChange();
    } else {
      this.timer = setTimeout(() => {
        this.triggerChange();
      }, WAIT_INTERVAL);
    }
  }

  update(newSearch) {
    this.searchUpdate(newSearch);
    this.triggerChange();
  }

  triggerChange() {
    if (this.props.onSearchUpdate) {
      this.props.onSearchUpdate(this.search);
    } else {
      console.warn("`onSearchUpdate` is not defined");
    }
  }

  handleKeyPress(event) {
    if (event.key === 'Enter') {
      this.triggerChange();
      clearTimeout(this.timer);
    }
  }

  searchUpdate(search) {
    this.search = search;
    this.setState({
      search: search
    });
  }

  render() {
    return (
      <div className='SearchBar'>
        <input
          className="Bar"
          placeholder="Search for..."
          value={this.state.search}
          onChange={(e) => this.handleInputChange(e)}
          onKeyPress={(e) => this.handleKeyPress(e)}
          type="search"
        />

      </div>
    );
  }
}
