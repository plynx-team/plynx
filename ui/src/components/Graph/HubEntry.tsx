import React, { Component } from 'react';
import { PLynxApi } from '../../API';
import HubEntryList from './HubEntryList';
// @ts-ignore
import ReactPaginate from 'react-paginate';
import LoadingScreen from '../LoadingScreen';
import SearchBar from '../Common/SearchBar';
import { NodeData } from '../../types';
import './style.css';

interface HubEntryHeaderProps {
  search: string;
  onUpdateFilter: (search: string) => void;
}

class HubEntryHeader extends Component<HubEntryHeaderProps> {
  search: string;

  constructor(props: HubEntryHeaderProps) {
    super(props);
    this.search = props.search;
  }

  handleSearchUpdate(search: string) {
    this.search = search;
    this.props.onUpdateFilter(search);
  }

  render() {
    return (
      <div className="hub-list-header">
        <div className="search">
          <SearchBar
            onSearchUpdate={(search) => this.handleSearchUpdate(search)}
            search={this.search}
          />
        </div>
      </div>
    );
  }
}

export interface HubEntryProps {
  hub: string;
  hubEntryItem: any;
  hiddenSearch?: string;
  history?: any;
}

interface HubEntryState {
  items: NodeData[];
  loading: boolean;
  pageCount: number;
  offset: number;
  search: string;
}

export default class HubEntry extends Component<HubEntryProps, HubEntryState> {
  perPage: number;
  mounted: boolean = false;
  nodeList: any = null;

  constructor(props: HubEntryProps) {
    super(props);
    this.state = {
      items: [],
      loading: true,
      pageCount: 0,
      offset: 0,
      search: '',
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
    let loading = true;
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    if (this.mounted) {
      this.setState({
        loading: true,
      });
    }

    const handleResponse = (response: any) => {
      const data = response.data;
      this.setState({
        items: data.items,
        pageCount: Math.ceil(data.total_count / this.perPage),
      });
      loading = false;
    };

    const handleError = (error: any) => {
      console.error(error);
      if (error.response && error.response.status === 401) {
        PLynxApi.getAccessToken().then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error('Could not refresh token');
            if (this.props.history) {
              this.props.history.push('/login/');
            } else {
              window.location.href = '/login';
            }
          }
        });
      }
    };

    while (loading) {
      await PLynxApi.endpoints.search_in_hubs
        .create({
          offset: this.state.offset,
          per_page: this.perPage,
          status: 'READY',
          hub: this.props.hub,
          search: `${this.props.hiddenSearch ? `${this.props.hiddenSearch} ` : ''}${this.state.search}`,
        })
        .then(handleResponse)
        .catch(handleError);
      if (loading) {
        await this.sleep(sleepPeriod);
        sleepPeriod = Math.min(sleepPeriod + sleepStep, sleepMaxPeriod);
      }
    }

    this.setState({
      loading: false,
    });
  }

  sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  handlePageClick = (data: { selected: number }) => {
    const selected = data.selected;
    const offset = Math.ceil(selected * this.perPage);

    this.setState({ offset }, () => {
      this.loadNodes();
    });
    if (this.nodeList && this.nodeList.scrollToTop) {
      this.nodeList.scrollToTop();
    }
  };

  handleUpdateFilter(search: string) {
    this.setState(
      {
        offset: 0,
        search,
      },
      () => {
        this.loadNodes();
      }
    );
  }

  render() {
    return (
      <div className="hub-list-content">
        {this.state.loading && <LoadingScreen style={{ width: '250px' }} />}
        <div className="hub-list-entry">
          <HubEntryHeader
            search={this.state.search}
            onUpdateFilter={(search) => this.handleUpdateFilter(search)}
          />
          <HubEntryList
            items={this.state.items}
            hubEntryItem={this.props.hubEntryItem}
            ref={(child: any) => {
              this.nodeList = child;
            }}
          />
          <ReactPaginate
            previousLabel="<"
            nextLabel=">"
            breakLabel={<div>...</div>}
            breakClassName="break-me"
            pageCount={this.state.pageCount}
            marginPagesDisplayed={2}
            pageRangeDisplayed={1}
            onPageChange={this.handlePageClick}
            containerClassName="pagination"
            activeClassName="active"
          />
        </div>
      </div>
    );
  }
}
