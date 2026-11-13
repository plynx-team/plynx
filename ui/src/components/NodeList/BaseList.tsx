import React, { Component, ReactNode } from 'react';
// @ts-ignore
import AlertContainer from '../3rd_party/react-alert';
import cookie from '../../cookie';
import { PLynxApi } from '../../api';
import List, { HeaderDescriptor } from './List';
// @ts-ignore
import ReactPaginate from 'react-paginate';
import LoadingScreen from '../LoadingScreen';
import {
  ACTIVE_NODE_RUNNING_STATUSES,
  ALERT_OPTIONS,
  COLLECTIONS,
  IAM_POLICIES,
  VIRTUAL_COLLECTIONS,
} from '../../constants';
import SearchBar from '../Common/SearchBar';
import {
  makeControlPanel,
  makeControlLink,
  makeControlButton,
  makeControlSeparator,
  PanelItem,
} from '../Common/ControlButton';
import { PluginsProvider, PluginsConsumer } from '../../contexts';
import { NodeData, PluginsDict } from '../../types';
import './list.css';
import '../controls.css';

export interface BaseListProps {
  children?: ReactNode;
  search?: string;
  collection: string;
  virtualCollection?: string;
  menuPanelDescriptor?: PanelItem[];
  extraSearch?: Record<string, any>;
  tag: string;
  header: HeaderDescriptor[];
  renderItem: (node: NodeData) => ReactNode;
  onUploadDialog?: (operation: any) => void;
  [key: string]: any;
}

interface BaseListState {
  items: NodeData[];
  loading: boolean;
  pageCount: number;
  resources_dict: Record<string, any>;
  search: string;
  offset: number;
  plugins_dict?: PluginsDict;
}

export default class BaseList extends Component<BaseListProps, BaseListState> {
  canCreateOperations: boolean;
  canCreateWorkflows: boolean;
  perPage: number;
  msg: any;
  mounted: boolean = false;
  refreshInterval: any;
  itemList: any;

  constructor(props: BaseListProps) {
    super(props);
    const user = cookie.load('user');
    let username = '';
    if (user) {
      username = user.username;
    } else {
      window.location.href = '/login';
    }

    let search = username ? `author:${username} ` : '';
    if (this.props.search) {
      search = this.props.search;
    }

    const policies = (user && user.policies) || [];
    this.canCreateOperations = policies.includes(IAM_POLICIES.CAN_CREATE_OPERATIONS);
    this.canCreateWorkflows = policies.includes(IAM_POLICIES.CAN_CREATE_WORKFLOWS);

    this.state = {
      items: [],
      loading: true,
      pageCount: 0,
      resources_dict: {},
      search,
      offset: 0,
    };
    this.perPage = 20;

    this.loadItems();
  }

  showAlert(message: string, type: string) {
    if (this.msg) {
      this.msg.show(message, {
        time: 5000,
        type: 'error',
        icon: <img src={`/alerts/${type}.svg`} width="32" height="32" alt={type} />,
      });
    }
  }

  componentDidMount() {
    this.mounted = true;
    if (this.props.collection === COLLECTIONS.RUNS) {
      this.refreshInterval = setInterval(() => {
        if (!this.mounted || this.state.loading) {
          return;
        }
        const hasActiveRuns = (this.state.items || []).some(
          (item) =>
            item.node_running_status &&
            ACTIVE_NODE_RUNNING_STATUSES.has(item.node_running_status.toUpperCase())
        );
        if (hasActiveRuns) {
          this.refreshItemsSilently();
        }
      }, 2000);
    }
  }

  componentWillUnmount() {
    this.mounted = false;
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  refreshItemsSilently() {
    PLynxApi.endpoints[`search_${this.props.collection}`]
      .create({
        offset: this.state.offset,
        per_page: this.perPage,
        search: this.state.search,
        ...this.props.extraSearch,
      })
      .then((response: any) => {
        if (!this.mounted) {
          return;
        }
        const data = response.data;
        this.setState({
          items: data.items,
          plugins_dict: data.plugins_dict,
          pageCount: Math.ceil(data.total_count / this.perPage),
        });
      })
      .catch(() => {});
  }

  async loadItems() {
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
        plugins_dict: data.plugins_dict,
        pageCount: Math.ceil(data.total_count / this.perPage),
      });
      loading = false;
      if (this.itemList && this.itemList.scrollToTop) {
        this.itemList.scrollToTop();
      }
    };

    const handleError = (error: any) => {
      if (error.response && error.response.status === 401) {
        PLynxApi.getAccessToken().then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error('Could not refresh token');
            window.location.href = '/login';
          } else {
            this.showAlert('Updated access token', 'success');
          }
        });
      } else {
        try {
          this.showAlert(error.response.data.message, 'failed');
        } catch {
          this.showAlert('Unknown error', 'failed');
        }
      }
    };

    while (loading) {
      await PLynxApi.endpoints[`search_${this.props.collection}`]
        .create({
          offset: this.state.offset,
          per_page: this.perPage,
          search: this.state.search,
          ...this.props.extraSearch,
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
      this.loadItems();
    });
  };

  handleSearchUpdate(search: string) {
    this.setState(
      {
        offset: 0,
        search,
      },
      () => {
        this.loadItems();
      }
    );
  }

  generateCreateDefs(plugins_info?: PluginsDict): PanelItem[] {
    if (!plugins_info || !this.props.virtualCollection) {
      return [];
    }
    if (this.props.virtualCollection === VIRTUAL_COLLECTIONS.OPERATIONS && !this.canCreateOperations) {
      return [];
    }
    if (this.props.virtualCollection === VIRTUAL_COLLECTIONS.WORKFLOWS && !this.canCreateWorkflows) {
      return [];
    }
    const result: PanelItem[] = [];
    const virtualDict = (plugins_info as any)[`${this.props.virtualCollection}_dict`] || {};

    const staticOperations = Object.values(virtualDict).filter((op: any) => op.is_static);
    for (const operation of staticOperations as any[]) {
      result.push({
        render: makeControlButton,
        props: {
          img: 'upload.svg',
          text: `Upload ${operation.title}`,
          func: () => {
            if (this.props.onUploadDialog) {
              this.props.onUploadDialog(plugins_info.operations_dict?.[operation.kind]);
            }
          },
          key: operation.kind,
        },
      });
    }

    if (result.length > 0) {
      result.push({
        render: makeControlSeparator,
        props: { key: 'separator_00' },
      });
    }

    const nonStaticOperations = Object.values(virtualDict).filter((op: any) => !op.is_static);
    for (const operation of nonStaticOperations as any[]) {
      result.push({
        render: makeControlLink,
        props: {
          img: 'plus.svg',
          text: operation.title,
          href: `/${this.props.collection}/${operation.kind}`,
          key: operation.kind,
        },
      });
    }

    return result;
  }

  render() {
    const menuItems = this.props.menuPanelDescriptor || [];

    return (
      <div className="ListPage">
        <PluginsProvider value={this.state.plugins_dict || { resources_dict: {}, executors_info: {} }}>
          {this.props.children}
          {this.state.loading && <LoadingScreen />}
          <AlertContainer ref={(a: any) => (this.msg = a)} {...ALERT_OPTIONS} />
          <PluginsConsumer>
            {(plugins_info: PluginsDict) =>
              makeControlPanel({
                props: {
                  items: [...menuItems, ...this.generateCreateDefs(plugins_info)],
                },
                children_func: () => (
                  <SearchBar
                    onSearchUpdate={(search) => this.handleSearchUpdate(search)}
                    search={this.state.search}
                  />
                ),
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
          <ReactPaginate
            previousLabel="Previous"
            nextLabel="Next"
            breakLabel={<div>...</div>}
            breakClassName="break-me"
            pageCount={this.state.pageCount}
            marginPagesDisplayed={2}
            pageRangeDisplayed={5}
            onPageChange={this.handlePageClick}
            containerClassName="pagination"
            activeClassName="active"
          />
        </PluginsProvider>
      </div>
    );
  }
}
