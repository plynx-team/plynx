import React, { Component } from 'react';
import ReactDOM from 'react-dom';
import AlertContainer from '../3rd_party/react-alert';
import cookie from 'react-cookies';
import { PLynxApi } from '../../API';
import List from './List';
import ReactPaginate from 'react-paginate';
import LoadingScreen from '../LoadingScreen';
import { ALERT_OPTIONS } from '../../constants';
import SearchBar from '../Common/SearchBar';
import {ResourceProvider} from '../../contexts';
import '../Common/ListPage.css';
import '../controls.css';


export default class ListPage extends Component {
  constructor(props) {
    super(props);
    document.title = this.props.title;
    const username = cookie.load('username');
    this.state = {
      items: [],
      loading: true,
      pageCount: 0,
      resources_dict: {},
      search: username ? 'author:' + username + ' ' : '',
    };
    this.perPage = 20;

    this.loadItems();
  }

  showAlert(message, type) {
    this.msg.show(message, {
      time: 5000,
      type: 'error',
      icon: <img src={"/alerts/" + type + ".svg"} width="32" height="32" alt={type}/>
    });
  }

  componentDidMount() {
    this.mounted = true;
  }

  componentWillUnmount() {
    this.mounted = false;
  }

  async loadItems() {
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

    function handleResponse(response) {
      const data = response.data;
      console.log(data.items);
      self.setState(
        {
          items: data.items,
          resources_dict: data.resources_dict,
          pageCount: Math.ceil(data.total_count / self.perPage)
        });
      loading = false;
      ReactDOM.findDOMNode(self.itemList).scrollTop = 0;
    }

    function handleError(error) {
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.props.history.push("/login/");
          } else {
            self.showAlert('Updated access token', 'success');
          }
        });
      } else {
          try {
            self.showAlert(error.response.data.message, 'failed');
          } catch {
            self.showAlert('Unknown error', 'failed');
          }
      }
    }

    /* eslint-disable no-await-in-loop */
    /* eslint-disable no-unmodified-loop-condition */
    while (loading) {
      await this.props.endpoint.create({
        offset: self.state.offset,
        per_page: self.perPage,
        search: self.state.search,
        ...this.props.extraSearch
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
    console.log(selected, offset);

    this.setState({offset: offset}, () => {
      this.loadItems();
    });
  };

  handleSearchUpdate(search) {
    this.setState({
      offset: 0,
      search: search,
    }, () => {
      this.loadItems();
    });
  }

  render() {
    return (
      <div className='ListPage'>
        <ResourceProvider value={this.state.resources_dict}>
            {this.props.children}
            {this.state.loading &&
              <LoadingScreen />
            }
            <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
            <div className="menu">
              {this.props.menu()}
            </div>
            <div className="search">
              <SearchBar
                  onSearchUpdate={(search) => this.handleSearchUpdate(search)}
                  search={this.state.search}
              />
            </div>
            <List
                header={this.props.header}
                items={this.state.items}
                       ref={(child) => {
                         this.itemList = child;
                       }}
                renderItem={this.props.renderItem}
                tag={this.props.tag}
            />
            <ReactPaginate previousLabel={"Previous"}
                           nextLabel={"Next"}
                           breakLabel={<div>...</div>}
                           breakClassName={"break-me"}
                           pageCount={this.state.pageCount}
                           marginPagesDisplayed={2}
                           pageRangeDisplayed={5}
                           onPageChange={this.handlePageClick}
                           containerClassName={"pagination"}
                           subContainerClassName={"pages pagination"}
                           activeClassName={"active"} />
        </ResourceProvider>
      </div>
    );
  }
}
