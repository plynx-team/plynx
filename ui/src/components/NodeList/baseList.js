import React, { Component } from 'react';
import ReactDOM from 'react-dom';
import AlertContainer from '../3rd_party/react-alert';
import cookie from 'react-cookies';
import { PLynxApi } from '../../API';
import List from './List';
import ReactPaginate from 'react-paginate';
import LoadingScreen from '../LoadingScreen';
import { ALERT_OPTIONS, IAM_POLICIES, VIRTUAL_COLLECTIONS } from '../../constants';
import SearchBar from '../Common/SearchBar';
import { makeControlPanel, makeControlLink, makeControlButton, makeControlSeparator } from '../Common/controlButton';
import {PluginsProvider, PluginsConsumer} from '../../contexts';
import PropTypes from 'prop-types';
import './list.css';
import '../controls.css';


export default class ListPage extends Component {
  static propTypes = {
    children: PropTypes.oneOfType([
      PropTypes.array.isRequired,
      PropTypes.object.isRequired,
    ]),
    search: PropTypes.string,
    collection: PropTypes.string.isRequired,
    virtualCollection: PropTypes.string,
    menuPanelDescriptor: PropTypes.array,
    extraSearch: PropTypes.object,
    tag: PropTypes.string.isRequired,
    header: PropTypes.array.isRequired,
    renderItem: PropTypes.func.isRequired,
    onUploadDialog: PropTypes.func,
  }


  constructor(props) {
    super(props);
    const user = cookie.load('user');
    let username = '';
    if (user) {
      username = user.username;
    }

    let search = username ? 'author:' + username + ' ' : '';
    if (this.props.search) {
      search = this.props.search;
    }

    this.canCreateOperations = user.policies.indexOf(IAM_POLICIES.CAN_CREATE_OPERATIONS) > -1;
    this.canCreateWorkflows = user.policies.indexOf(IAM_POLICIES.CAN_CREATE_WORKFLOWS) > -1;

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
            window.location = '/login';
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
      await PLynxApi.endpoints[`search_${this.props.collection}`].create({
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

  generateCreateDefs(plugins_info) {
    if (!plugins_info || !this.props.virtualCollection) {
      return [];
    }
    if (this.props.virtualCollection === VIRTUAL_COLLECTIONS.OPERATIONS && !this.canCreateOperations) {
      return [];
    }
    if (this.props.virtualCollection === VIRTUAL_COLLECTIONS.WORKFLOWS && !this.canCreateWorkflows) {
      return [];
    }
    const result = [];
    result.push(
        ...Object.values(plugins_info[`${this.props.virtualCollection}_dict`])
            .filter((operation) => operation.is_static).map(
              (operation) => {
                return {
                  render: makeControlButton,
                  props: {
                    img: 'upload.svg',
                    text: `Upload ${operation.title}`,
                    func: () => {
                      this.props.onUploadDialog(plugins_info.operations_dict[operation.kind]);
                    },
                    key: operation.kind
                  },
                };
              }
          )
    );
    if (result.length > 0) {
      result.push({
        render: makeControlSeparator,
        props: {key: 'separator_00'}
      },);
    }
    result.push(
        ...Object.values(plugins_info[`${this.props.virtualCollection}_dict`])
            .filter((operation) => ! operation.is_static).map(
              (operation) => {
                return {
                  render: makeControlLink,
                  props: {
                    img: 'plus.svg',
                    text: operation.title,
                    href: `/${this.props.collection}/${operation.kind}`,
                    key: operation.kind
                  },
                };
              }
          )
    );

    return result;
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
            <PluginsConsumer>
            {
                plugins_info => makeControlPanel({
                  props: {
                    items: [...this.props.menuPanelDescriptor, ...this.generateCreateDefs(plugins_info)],
                  },
                  children_func: () => {
                    return <SearchBar
                                    onSearchUpdate={(search) => this.handleSearchUpdate(search)}
                                    search={this.state.search}
                                    />;
                  }
                })
            }
            </PluginsConsumer>
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
