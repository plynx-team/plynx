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
import { makeControlPanel } from '../Common/controlButton';
import {PluginsProvider, PluginsConsumer} from '../../contexts';
import PropTypes from 'prop-types';
import './list.css';
import '../controls.css';


export default class ListPage extends Component {
  static propTypes = {
    search: PropTypes.string,
    virtualCollection: PropTypes.string,
    children: PropTypes.array,
    menuPanelDescriptor: PropTypes.array,
    extraSearch: PropTypes.object,
    tag: PropTypes.string.isRequired,
    header: PropTypes.array.isRequired,
    renderItem: PropTypes.func.isRequired,
    endpoint: PropTypes.shape({
      create: PropTypes.func.isRequired,
    }),
  }


  constructor(props) {
    super(props);
    const username = cookie.load('username');
    let search = username ? 'author:' + username + ' ' : '';
    if (this.props.search) {
      search = this.props.search;
    }
    this.state = {
      items: [],
      loading: true,
      pageCount: 0,
      resources_dict: {},
      search: search,
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
          plugins_dict: data.plugins_dict,
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
        <PluginsProvider value={this.state.plugins_dict}>
            {this.props.children}
            {this.state.loading &&
              <LoadingScreen />
            }
            <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
            {
                makeControlPanel({
                    props: {
                        items: [...this.props.menuPanelDescriptor, ...(this.state.plugins_dict ? this.props.pluginsDictMenuTransformer(this.state.plugins_dict): [])],
                    },
                    children_func: () => {
                        return <SearchBar
                                onSearchUpdate={(search) => this.handleSearchUpdate(search)}
                                search={this.state.search}
                                />
                            }
                } )
            }
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
        </PluginsProvider>
      </div>
    );
  }
}
