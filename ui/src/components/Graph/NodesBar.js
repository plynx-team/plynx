// src/components/About/index.js
import React, { Component } from 'react';
import ReactDOM from 'react-dom';
import { PLynxApi } from '../../API';
import NodeBarHeader from './NodeBarHeader';
import NodeBarList from './NodeBarList';
import ReactPaginate from 'react-paginate';
import LoadingScreen from '../LoadingScreen';
import { OPERATIONS } from '../../constants';
import './style.css';

export default class NodesBar extends Component {
  constructor(props) {
    super(props);
    this.state = {
      items: [],
      loading: true,
      pageCount: 0,
      selectedTab: 'operations',
      baseNodeNames: OPERATIONS,
      offset: 0,
      search: "sort:starred ",
    };
    this.perPage = 20;

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
          items: data.nodes,
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
      await PLynxApi.endpoints.nodes.getAll({
        query: {
          offset: self.state.offset,
          per_page: self.perPage,
          status: "READY",
          base_node_names: self.state.baseNodeNames,
          search: this.state.search,
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

    this.setState({offset: offset}, () => {
      this.loadNodes();
    });
    ReactDOM.findDOMNode(this.nodeList).scrollTop = 0;
  };

  handleUpdateFilter(tabName, baseNodeNames, search) {
    this.setState({
      selectedTab: tabName,
      baseNodeNames: baseNodeNames,
      offset: 0,
      search: search,
    }, () => {
      this.loadNodes();
    });
  }

  render() {
    return (
      <div className="NodesBar">
        {this.state.loading &&
          <LoadingScreen style={{ width: '250px' }}/>
        }
        <div className="NodesBarInner">
          <NodeBarHeader
            selectedTab={this.state.selectedTab}
            onUpdateFilter={(tabName, baseNodeNames, search) => this.handleUpdateFilter(tabName, baseNodeNames, search)}
            search={this.state.search}
            />
          <NodeBarList items={this.state.items}
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
