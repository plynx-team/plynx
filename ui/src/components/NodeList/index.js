import React, { Component } from 'react';
import ReactDOM from 'react-dom';
import AlertContainer from 'react-alert-es6';
import cookie from 'react-cookies';
import { PLynxApi } from '../../API';
import List from './List';
import ReactPaginate from 'react-paginate';
import LoadingScreen from '../LoadingScreen';
import { ALERT_OPTIONS, OPERATIONS } from '../../constants';
import SearchBar from '../Common/SearchBar';
import './style.css';
import '../Common/ListPage.css';
import '../controls.css';


export default class ListPage extends Component {
  constructor(props) {
    super(props);
    document.title = "Node List - PLynx";
    const username = cookie.load('username');
    this.state = {
      nodes: [],
      loading: true,
      pageCount: 0,
      search: username ? 'author:' + username + ' ' : '',
    };
    this.perPage = 20;

    this.loadNodes();
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

    function handleResponse(response) {
      const data = response.data;
      console.log(data.nodes);
      self.setState(
        {
          nodes: data.nodes,
          pageCount: Math.ceil(data.total_count / self.perPage)
        });
      loading = false;
      ReactDOM.findDOMNode(self.nodeList).scrollTop = 0;
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
      }
    }

    /* eslint-disable no-await-in-loop */
    /* eslint-disable no-unmodified-loop-condition */
    while (loading) {
      await PLynxApi.endpoints.nodes.getAll({
        query: {
          offset: self.state.offset,
          per_page: self.perPage,
          base_node_names: OPERATIONS,
          search: self.state.search,
        }
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
      this.loadNodes();
    });
  };

  handleSearchUpdate(search) {
    this.setState({
      offset: 0,
      search: search,
    }, () => {
      this.loadNodes();
    });
  }

  render() {
    return (
      <div className='ListPage'>
        {this.state.loading &&
          <LoadingScreen />
        }
        <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
        <div className="menu">
          <a className="menu-button" href="/nodes/new">
            {"Create new Operation"}
          </a>
        </div>
        <div className="search">
          <SearchBar
              onSearchUpdate={(search) => this.handleSearchUpdate(search)}
              search={this.state.search}
          />
        </div>
        <List nodes={this.state.nodes}
                   ref={(child) => {
                     this.nodeList = child;
                   }}/>
        <ReactPaginate previousLabel={"Previous"}
                       nextLabel={"Next"}
                       breakLabel={<a>...</a>}
                       breakClassName={"break-me"}
                       pageCount={this.state.pageCount}
                       marginPagesDisplayed={2}
                       pageRangeDisplayed={5}
                       onPageChange={this.handlePageClick}
                       containerClassName={"pagination"}
                       subContainerClassName={"pages pagination"}
                       activeClassName={"active"} />
      </div>
    );
  }
}
