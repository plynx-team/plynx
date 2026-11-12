import React, { Component, ChangeEvent, KeyboardEvent } from 'react';
import OutlinedInput from '@mui/material/OutlinedInput';
import InputAdornment from '@mui/material/InputAdornment';
import SearchIcon from '@mui/icons-material/Search';
import Box from '@mui/material/Box';
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
      <Box className="SearchBar" sx={{ display: 'inline-flex', width: '100%' }}>
        <OutlinedInput
          className="Bar"
          fullWidth
          size="small"
          placeholder={this.props.placeholder || 'Search for...'}
          value={this.state.search}
          onChange={(e: ChangeEvent<HTMLInputElement>) => this.handleInputChange(e)}
          onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => this.handleKeyPress(e)}
          autoFocus={this.props.autoFocus !== false}
          startAdornment={
            <InputAdornment position="start" sx={{ marginRight: '6px' }}>
              <SearchIcon fontSize="small" sx={{ color: '#888', width: 18, height: 18 }} />
            </InputAdornment>
          }
          sx={{
            height: '32px',
            backgroundColor: '#2b2b2b',
            color: '#fff',
            fontSize: '0.9rem',
            borderRadius: '3px',
            paddingLeft: '8px',
            '& .MuiOutlinedInput-input': {
              padding: '4px 6px 4px 0',
            },
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: '#444',
            },
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: '#666',
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: '#2196F3',
            },
          }}
        />
      </Box>
    );
  }
}
