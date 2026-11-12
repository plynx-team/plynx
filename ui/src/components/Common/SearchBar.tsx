import React, { Component, ChangeEvent, KeyboardEvent } from 'react';
import './SearchBar.css';

const WAIT_INTERVAL = 400;

export interface SearchBarProps {
  search: string;
  onSearchUpdate: (search: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
}

interface SearchBarState {
  search: string;
}

export default class SearchBar extends Component<SearchBarProps, SearchBarState> {
  search: string;
  timer: any = null;

  constructor(props: SearchBarProps) {
    super(props);
    this.search = this.props.search || '';
    this.state = {
      search: this.search,
    };
  }

  componentDidUpdate(prevProps: SearchBarProps) {
    if (prevProps.search !== this.props.search && this.props.search !== this.state.search) {
      this.searchUpdate(this.props.search || '');
    }
  }

  componentWillUnmount() {
    if (this.timer) {
      clearTimeout(this.timer);
    }
  }

  handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    clearTimeout(this.timer);

    const value = event.target.value;
    this.searchUpdate(value);

    if (value === '') {
      this.triggerChange();
    } else {
      this.timer = setTimeout(() => {
        this.triggerChange();
      }, WAIT_INTERVAL);
    }
  }

  update(newSearch: string) {
    this.searchUpdate(newSearch);
    this.triggerChange();
  }

  triggerChange() {
    if (this.props.onSearchUpdate) {
      this.props.onSearchUpdate(this.search);
    } else {
      console.warn('`onSearchUpdate` is not defined');
    }
  }

  handleKeyPress(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      this.triggerChange();
      clearTimeout(this.timer);
    }
  }

  searchUpdate(search: string) {
    this.search = search;
    this.setState({
      search,
    });
  }

  render() {
    return (
      <div className="SearchBar">
        <input
          className="Bar"
          placeholder={this.props.placeholder || 'Search for...'}
          value={this.state.search}
          onChange={(e) => this.handleInputChange(e)}
          onKeyDown={(e) => this.handleKeyPress(e)}
          type="search"
          autoFocus={this.props.autoFocus !== false}
        />
      </div>
    );
  }
}
