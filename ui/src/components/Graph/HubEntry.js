/* eslint max-classes-per-file: 0 */
import React, { Component } from 'react';
import ReactDOM from 'react-dom';
import PropTypes from 'prop-types';
import { PLynxApi } from '../../API';
import HubEntryList from './HubEntryList';
import ReactPaginate from 'react-paginate';
import LoadingScreen from '../LoadingScreen';
import SearchBar from '../Common/SearchBar';
import './style.css';

class HubEntryHeader extends Component {
  static propTypes = {
    search: PropTypes.string.isRequired,
    onUpdateFilter: PropTypes.func.isRequired,
  };

  constructor(props) {
    super(props);
    this.search = props.search;
    this.initialSearch = props.search;
  }

  handleSearchUpdate(search) {
    this.search = search;
    this.props.onUpdateFilter(search);
  }

  render() {
    return (
      <div className="hub-list-header">
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

export default class HubEntry extends Component {
  static propTypes = {
    hub: PropTypes.string.isRequired,
    hubEntryItem: PropTypes.func.isRequired,
    hiddenSearch: PropTypes.string,
  };

  constructor(props) {
    super(props);
    this.state = {
      items: [],
      loading: true,
      pageCount: 0,
      offset: 0,
      search: "",
    };
    this.perPage = 30;

    this.loadNodes();
  }

  componentDidMount() {
    this.mounted = true;
  }

  componentWillUnmount() {
    this.mounted = false;
  }

  async loadNodes() {
    // Loading

    const self = this;
    let loading = true;
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    if (this.mounted) {
      self.setState({
        loading: true,
      });
    }

    const handleResponse = (response) => {
      const data = response.data;
      console.log(data);
      self.setState(
        {
          items: data.items,
          pageCount: Math.ceil(data.total_count / self.perPage)
        });
      loading = false;
    };

    const handleError = (error) => {
      console.error(error);
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.props.history.push("/login/");
          } else {
            console.log('Updated access token', 'success');
          }
        });
      }
    };

    /* eslint-disable no-await-in-loop */
    /* eslint-disable no-unmodified-loop-condition */
    while (loading) {
      await PLynxApi.endpoints.search_in_hubs.create({
        offset: self.state.offset,
        per_page: self.perPage,
        status: "READY",
        hub: this.props.hub,
        search: `${this.props.hiddenSearch ? this.props.hiddenSearch + " ": ""}${this.state.search}`,
      })
      .then(handleResponse)
      .catch(handleError);
      if (loading) {
        await self.sleep(sleepPeriod);
        sleepPeriod = Math.min(sleepPeriod + sleepStep, sleepMaxPeriod);
      }
    }
    /* eslint-enable no-unmodified-loop-condition */
    /* eslint-enable no-await-in-loop */

    // Stop loading
    self.setState({
      loading: false,
    });
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  handlePageClick = (data) => {
    const selected = data.selected;
    const offset = Math.ceil(selected * this.perPage);

    this.setState({offset: offset}, () => {
      this.loadNodes();
    });
    ReactDOM.findDOMNode(this.nodeList).scrollTop = 0;
  };

  handleUpdateFilter(search) {
    this.setState({
      offset: 0,
      search: search,
    }, () => {
      this.loadNodes();
    });
  }

  render() {
    return (
      <div className="hub-list-content">
        {this.state.loading &&
          <LoadingScreen style={{ width: '250px' }}/>
        }
        <div className="hub-list-entry">
          <HubEntryHeader
            search={this.state.search}
            onUpdateFilter={(search) => this.handleUpdateFilter(search)}
            />
          <HubEntryList items={this.state.items}
                        hubEntryItem={this.props.hubEntryItem}
                        ref={(child) => {
                          this.nodeList = child;
                        }}/>
          <ReactPaginate previousLabel={"<"}
                         nextLabel={">"}
                         breakLabel={<div>...</div>}
                         breakClassName={"break-me"}
                         pageCount={this.state.pageCount}
                         marginPagesDisplayed={2}
                         pageRangeDisplayed={1}
                         onPageChange={this.handlePageClick}
                         containerClassName={"pagination"}
                         subContainerClassName={"pages pagination"}
                         activeClassName={"active"}
                         key={this.state.selectedTab}/>
        </div>
      </div>
    );
  }
}
