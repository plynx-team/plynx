import React, { Component } from 'react';
import Tour from '../Common/Tour';
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../api';
import cookie from '../../cookie';
import LoadingScreen from '../LoadingScreen';
import {
  ACTION,
  RELOAD_OPTIONS,
  RESPONCE_STATUS,
  ALERT_OPTIONS,
  VALIDATION_CODES,
  VALIDATION_TARGET_TYPE,
  NODE_STATUS,
  NODE_RUNNING_STATUS,
  COLLECTIONS,
  ACTIVE_NODE_RUNNING_STATUSES,
} from '../../constants';
import Graph from '../Graph';
import Node from '../Node';
import RunList from '../NodeList/RunList';
import DeprecateDialog from '../Dialogs/DeprecateDialog';
import TextViewDialog from '../Dialogs/TextViewDialog';
import FileUploadDialog from '../Dialogs/FileUploadDialog';
import { PluginsProvider, PluginsConsumer } from '../../contexts';
import { makeControlPanel, makeControlCheckbox, makeControlToggles, makeControlButton, makeControlSeparator } from '../Common/ControlButton';
import { addStyleToTourSteps } from '../../utils';
import { ReactFlowProvider } from 'reactflow';
import { RouterHistory, RouterLocation } from '../../router';
import { NodeData, PluginsDict } from '../../types';
import './style.css';

export const VIEW_MODE = Object.freeze({
  NONE: 'none',
  GRAPH: 0,
  NODE: 1,
  RUNS: 2,
});

const FIRST_TIME_APPROVED_STATE = 'first_time_approved_state';
const UPDATE_TIMEOUT = 1000;

export interface EditorProps {
  history: RouterHistory;
  location: RouterLocation;
  collection: string;
  match: {
    params: {
      node_id?: string;
    };
  };
}

export interface EditorState {
  editable: boolean;
  loading: boolean;
  view_mode: number | string;
  deprecateQuestionDialog: boolean;
  deprecateParentDialog: boolean;
  collection: string | null;
  tourSteps: any[];
  activeStatus: boolean;
  uploadOperation: any;
  node?: NodeData | any;
  plugins_dict?: PluginsDict;
  selectedNode?: string;
  is_graph?: boolean;
  is_workflow?: boolean;
  preview_text?: string | null;
  generatedCode?: string;
  error_message?: any;
}

export default class Editor extends Component<EditorProps, EditorState> {
  node: any;
  graphComponent: any;
  nodeComponent: any;
  runsComponent: any;
  msg: any;
  tour_steps: any[];
  schedule: ReturnType<typeof setTimeout> | null;
  syncInterval: ReturnType<typeof setInterval> | null;
  timeout: ReturnType<typeof setTimeout> | null;
  last_run_is_in_finished_status: boolean;

  constructor(props: EditorProps) {
    super(props);

    this.state = {
      editable: false,
      loading: true,
      view_mode: VIEW_MODE.NONE,
      deprecateQuestionDialog: false,
      deprecateParentDialog: false,
      collection: null,
      tourSteps: [],
      activeStatus: false,
      uploadOperation: null,
    };

    let token = cookie.load('refresh_token');
    // TODO remove after demo
    if (token === 'Not assigned') {
      token = cookie.load('access_token');
    }

    this.tour_steps = [];
    this.schedule = null;
    this.syncInterval = null;
    this.timeout = null;
    this.last_run_is_in_finished_status = false;
    console.log((globalThis as any).appVersion);
  }

  sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  updateNode(node: any, force?: boolean) {
    this.node = node;
    document.title = (this.node?.title || '') + ' - PLynx';

    this.setState({
      node: this.node,
      editable: !this.node._readonly && this.props.collection === COLLECTIONS.TEMPLATES && this.node.node_status.toUpperCase() === NODE_STATUS.CREATED,
      collection: this.props.collection,
      activeStatus: this.props.collection === COLLECTIONS.RUNS && ACTIVE_NODE_RUNNING_STATUSES.has(this.node.node_running_status),
    });
    if (this.graphComponent) {
      if (force) {
        this.graphComponent.loadGraphFromJson(this.node);
      } else {
        this.graphComponent.updateGraphFromJson(this.node);
      }
    }
  }

  async componentDidMount() {
    let loading = true;
    const rawNodeId = this.props.match?.params?.node_id || '';
    const node_id = rawNodeId.replace(/\$+$/, '');
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    const loadNode = (response: any) => {
      const searchParams = new URLSearchParams(this.props.location.search);
      const subNodeIds = searchParams.getAll('sub_node_id');
      let node = response.data.node;

      if (subNodeIds.length > 0) {
        let sub_nodes: any[] | null = null;
        for (let sub_node_id of subNodeIds) {
          sub_node_id = sub_node_id.replace(/^\$+|\$+$/g, '');
          for (let i = 0; i < node.parameters.length; ++i) {
            if (node.parameters[i].name === '_nodes') {
              sub_nodes = node.parameters[i].value.value;
              break;
            }
          }
          if (sub_nodes) {
            for (const sub_node of sub_nodes) {
              if (sub_node._id === sub_node_id) {
                node = sub_node;
                break;
              }
            }
          }
        }
      }

      this.updateNode(node, true);

      const executor_info = response.data.plugins_dict?.executors_info?.[this.node.kind];
      console.log('plugins_dict', response.data.plugins_dict);
      const is_graph = executor_info?.is_graph ?? false;

      let view_mode: number | string = is_graph ? VIEW_MODE.GRAPH : VIEW_MODE.NODE;
      if (searchParams.has('view_mode')) {
        view_mode = Math.max(parseInt(searchParams.get('view_mode') || '0', 10), is_graph ? 0 : 1);
      }
      const selectedNode = searchParams.get('nid') || undefined;

      this.setState({
        plugins_dict: response.data.plugins_dict,
        view_mode: view_mode,
        selectedNode: selectedNode,
        is_graph: is_graph,
        is_workflow: Object.prototype.hasOwnProperty.call(response.data.plugins_dict.workflows_dict, node.kind),
      });

      this.tour_steps = addStyleToTourSteps(response.data.tour_steps || []);

      console.log('node_id:', node_id);
      if (!node_id.startsWith(this.node._id) && subNodeIds.length === 0) {
        this.props.history.replace('/' + this.props.collection + '/' + this.node._id + '$');
      }

      this.initializeUpdate();

      const first_time_approved_node_id = window.sessionStorage.getItem(FIRST_TIME_APPROVED_STATE);
      if (first_time_approved_node_id === this.node._id) {
        this.setState({ deprecateParentDialog: true });
      }
      if (first_time_approved_node_id) {
        window.sessionStorage.removeItem('first_time_approved_state');
      }

      loading = false;

      if (cookie.load('showTour')) {
        setTimeout(() => this.handleTour(), 1000);
        cookie.remove('showTour', { path: '/' });
      }

      if (!this.node.auto_sync || this.state.collection !== COLLECTIONS.TEMPLATES) {
        if (this.graphComponent) {
          this.graphComponent.clearCacheNodes();
        }
      }
    };

    const syncNode = (response: any) => {
      const node = response.data.node;

      console.log('New run_id', node.latest_run_id);
      this.node.latest_run_id = node.latest_run_id;
      this.last_run_is_in_finished_status = response.data.last_run_is_in_finished_status;

      let sub_nodes: any[] | null = null;
      for (let i = 0; i < node.parameters.length; ++i) {
        if (node.parameters[i].name === '_nodes') {
          sub_nodes = node.parameters[i].value.value;
          break;
        }
      }
      if (sub_nodes === null) {
        return;
      }

      if (this.graphComponent) {
        this.graphComponent.syncNodes(sub_nodes);
      }
    };

    const handleError = (error: any) => {
      console.error(error);
      console.error('-----------');
      if (!error.response) {
        this.setState({ error_message: error });
      } else if (error.response.status === 403) {
        this.props.history.replace('/permission_denied');
        window.location.reload();
        loading = false;
      } else if (error.response.status === 404) {
        this.props.history.replace('/not_found');
        window.location.reload();
        loading = false;
      } else if (error.response.status === 401) {
        PLynxApi.getAccessToken().then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error('Could not refresh token');
            window.location.href = '/login';
          } else {
            this.showAlert('Updated access token', 'success');
          }
        });
      }
    };

    while (loading) {
      await PLynxApi.endpoints[this.props.collection]
        .getOne({ id: node_id })
        .then(loadNode)
        .catch(handleError);
      if (loading) {
        await this.sleep(sleepPeriod);
        sleepPeriod = Math.min(sleepPeriod + sleepStep, sleepMaxPeriod);
      }
    }

    // Stop loading
    this.setState({
      loading: false,
    });

    this.syncInterval = setInterval(() => {
      if (this.state.collection !== COLLECTIONS.TEMPLATES) {
        return;
      }
      if (!this.state.node || !this.state.node.auto_sync) {
        return;
      }
      if (this.schedule || !this.node.latest_run_id || this.last_run_is_in_finished_status) {
        return;
      }
      if (!this.state.is_workflow) {
        return;
      }

      console.log('Run sync', 'latest_run_id', this.node.latest_run_id);

      PLynxApi.endpoints[this.props.collection]
        .getOne({ id: this.node._id })
        .then(syncNode)
        .catch(handleError);
    }, 1000);
  }

  componentWillUnmount() {
    if (this.timeout) {
      clearTimeout(this.timeout);
    }

    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }
  }

  checkNodeStatus() {
    const node_id = this.node._id;
    PLynxApi.endpoints[this.props.collection]
      .getOne({ id: node_id })
      .then((response: any) => {
        this.updateNode(response.data.node, false);
        this.initializeUpdate();
      })
      .catch((error: any) => {
        console.log(error);
        if (error.response?.status === 401) {
          PLynxApi.getAccessToken().then((isSuccessfull) => {
            if (isSuccessfull) {
              this.timeout = setTimeout(() => this.checkNodeStatus(), UPDATE_TIMEOUT);
            } else {
              console.error('Could not refresh token');
              window.location.href = '/login';
            }
          });
        }
      });
  }

  initializeUpdate() {
    const node_running_status = this.node.node_running_status.toUpperCase();
    if (this.props.collection === COLLECTIONS.RUNS && ACTIVE_NODE_RUNNING_STATUSES.has(node_running_status)) {
      this.timeout = setTimeout(() => this.checkNodeStatus(), UPDATE_TIMEOUT);
    }
  }

  postNode({ node, reloadOption, action, retryOnAuth = true, silent = false }: {
    node: any;
    reloadOption?: string;
    action?: string;
    retryOnAuth?: boolean;
    silent?: boolean;
  }) {
    if (!silent) {
      this.setState({ loading: true });
      console.log(action, node);
    }

    PLynxApi.endpoints[this.props.collection]
      .create({
        node: node,
        action: action,
      })
      .then((response: any) => {
        const data = response.data;
        this.setState({ loading: false });
        if (data.status === RESPONCE_STATUS.SUCCESS) {
          if (reloadOption === RELOAD_OPTIONS.RELOAD) {
            if (action === ACTION.APPROVE && node.parent_node_id) {
              window.sessionStorage.setItem(FIRST_TIME_APPROVED_STATE, node._id);
            }
            window.location.reload();
          } else if (reloadOption === RELOAD_OPTIONS.OPEN_NEW_LINK) {
            this.props.history.push(response.data.url);
          }

          if (action === ACTION.SAVE) {
            if (data.latest_run_id) {
              this.node.latest_run_id = data.latest_run_id;
              this.last_run_is_in_finished_status = false;
            }
            if (!silent) {
              this.showAlert('Saved', 'success');
            }
          } else if (action === ACTION.VALIDATE) {
            this.showAlert('Valid', 'success');
          } else if (action === ACTION.PREVIEW_CMD) {
            this.setState({ preview_text: data.preview_text });
          } else if (action === ACTION.UPGRADE_NODES) {
            this.updateNode(data.node, true);
            console.log('new', data.node);
            let message = '';
            if (data.upgraded_nodes_count > 0) {
              message = 'Upgraded ' + data.upgraded_nodes_count + (data.upgraded_nodes_count > 1 ? ' Nodes' : ' Node');
            } else {
              message = 'No Nodes upgraded';
            }
            this.showAlert(message, 'success');
          } else if (action === ACTION.REARRANGE_NODES) {
            this.updateNode(data.node, true);
            console.log('rearranged', data.node);
          } else if (action === ACTION.GENERATE_CODE) {
            this.setState({
              generatedCode: data.code,
            });
          } else if (action === ACTION.CREATE_RUN) {
            this.showAlert('Created new run with id: ' + response.data.run_id, 'success');
            this.node.latest_run_id = response.data.run_id;
            if (this.state.node?.auto_sync) {
              this.last_run_is_in_finished_status = false;
            } else {
              window.open(`/${COLLECTIONS.RUNS}/${response.data.run_id}`, '_blank');
            }
          }
        } else if (data.status === RESPONCE_STATUS.VALIDATION_FAILED) {
          console.warn(data.message);
          this.showValidationError(data.validation_error);
          this.showAlert(data.message, 'failed');
        } else {
          console.warn(data.message);
          this.showAlert(data.message, 'failed');
        }
      })
      .catch((error: any) => {
        console.log(error);
        if (error.response?.status === 401) {
          PLynxApi.getAccessToken().then((isSuccessfull) => {
            if (!isSuccessfull) {
              console.error('Could not refresh token');
              this.showAlert('Failed to authenticate', 'failed');
            } else if (retryOnAuth) {
              this.postNode({ node: node, reloadOption: reloadOption, action: action, retryOnAuth: false });
            } else {
              this.showAlert('Failed to save the graph, please try again', 'failed');
            }
          });
        } else {
          try {
            this.showAlert(error.response.data.message, 'failed');
          } catch {
            this.showAlert('Unknown error', 'failed');
          }
        }
        this.setState({ loading: false });
      });
  }

  showValidationError(validationError: any) {
    if (validationError.target === VALIDATION_TARGET_TYPE.GRAPH) {
      if (this.graphComponent) {
        this.graphComponent.showValidationError(validationError);
      } else {
        this.showAlert('Errors in the graph structure', 'failed');
      }
      return;
    }

    const children = validationError.children || [];
    for (let i = 0; i < children.length; ++i) {
      const child = children[i];
      switch (child.validation_code) {
        case VALIDATION_CODES.IN_DEPENDENTS:
          this.showValidationError(child);
          break;
        case VALIDATION_CODES.MISSING_PARAMETER:
          this.showAlert('Missing parameter `' + child.object_id + '`', 'warning');
          break;
        case VALIDATION_CODES.MINIMUM_COUNT_MUST_NOT_BE_NEGATIVE:
          this.showAlert(`Minimum count of inputs cannot be negative. Input: '${child.object_id}'`, 'warning');
          break;
        case VALIDATION_CODES.MAXIMUM_COUNT_MUST_BE_GREATER_THAN_MINIMUM:
          this.showAlert(`Minimum number of inputs is greater than maximum. Input: '${child.object_id}'`, 'warning');
          break;
        case VALIDATION_CODES.MAXIMUM_COUNT_MUST_NOT_BE_ZERO:
          this.showAlert(`Maximum number of inputs cannot be 0. Input: '${child.object_id}'`, 'warning');
          break;
        default:
          this.showAlert(`${child.validation_code}. Input: '${child.object_id}'`, 'warning');
      }
    }
  }

  showAlert(message: string, type: string) {
    if (this.msg) {
      this.msg.show(message, {
        time: 5000,
        type: 'error',
        icon: <img src={'/alerts/' + type + '.svg'} width="32" height="32" alt="alert" />,
      });
    }
  }

  scheduleUpdate(delay: number) {
    if (this.schedule) {
      return;
    }
    this.schedule = setTimeout(() => this.runScheduledUpdate(), delay);
  }

  disableScheduledUpdate() {
    this.schedule = null;
  }

  runScheduledUpdate() {
    this.disableScheduledUpdate();
    this.postNode({
      node: this.node,
      action: ACTION.SAVE,
      reloadOption: RELOAD_OPTIONS.NONE,
      silent: true,
    });
  }

  handleNodeChange(node: any) {
    const shouldSave = this.node?.auto_sync || node?.auto_sync;

    if (this.state.collection !== COLLECTIONS.TEMPLATES) {
      return;
    }
    this.node = node;
    this.last_run_is_in_finished_status = false;

    if (shouldSave) {
      this.scheduleUpdate(100);
    }
  }

  handleSave() {
    console.log('to_save', this.node);
    this.postNode({
      node: this.node,
      action: ACTION.SAVE,
      reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handlePreview() {
    this.postNode({
      node: this.node,
      action: ACTION.PREVIEW_CMD,
      reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleValidate() {
    this.postNode({
      node: this.node,
      action: ACTION.VALIDATE,
      reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleRun() {
    this.postNode({
      node: this.node,
      action: ACTION.CREATE_RUN,
      reloadOption: RELOAD_OPTIONS.NEW_TAB,
    });
  }

  handleApprove() {
    this.postNode({
      node: this.node,
      action: ACTION.APPROVE,
      reloadOption: RELOAD_OPTIONS.RELOAD,
    });
  }

  handleGenerateCode() {
    this.postNode({
      node: this.node,
      action: ACTION.GENERATE_CODE,
      reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleUpgradeNodes() {
    this.postNode({
      node: this.node,
      action: ACTION.UPGRADE_NODES,
      reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleRearrangeNodes() {
    this.postNode({
      node: this.node,
      action: ACTION.REARRANGE_NODES,
      reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleCancel() {
    this.postNode({
      node: this.node,
      action: ACTION.CANCEL,
      reloadOption: RELOAD_OPTIONS.NONE,
    });
  }

  handleClone() {
    this.postNode({
      node: this.node,
      action: ACTION.CLONE,
      reloadOption: RELOAD_OPTIONS.OPEN_NEW_LINK,
    });
  }

  handleChangeNodeParameter(parameterName: string, event: React.ChangeEvent<HTMLInputElement>) {
    const target = event.target;
    const value = target.type === 'checkbox' ? target.checked : target.value;

    this.node[parameterName] = value;
    this.updateNode(this.node, false);

    if (parameterName === 'auto_sync') {
      if (value === false) {
        if (this.graphComponent) {
          this.graphComponent.clearCacheNodes();
        }
      }
      this.handleSave();
    }
  }

  handleDeprecateClick() {
    this.setState({ deprecateQuestionDialog: true });
  }

  handleDeprecate(node: any, action: string) {
    this.postNode({
      node: node,
      action: action,
      reloadOption: RELOAD_OPTIONS.RELOAD,
    });
  }

  handleCloseDeprecateDialog() {
    this.setState({
      deprecateQuestionDialog: false,
      deprecateParentDialog: false,
    });
  }

  handleSetViewMode(view_mode: number | string) {
    this.setState({ view_mode: view_mode });
    const searchParams = new URLSearchParams(this.props.location.search);
    searchParams.set('view_mode', String(view_mode));

    this.props.history.push({
      search: '?' + searchParams.toString(),
    });
  }

  handleTour() {
    let tourSteps: any[] = [];
    if (this.graphComponent) {
      tourSteps = this.graphComponent.tourSteps || [];

      if (this.tour_steps.length > 0) {
        tourSteps = tourSteps.concat(this.tour_steps);
      }
    }
    if (this.nodeComponent) {
      tourSteps = this.nodeComponent.tourSteps || [];
    }
    if (this.runsComponent) {
      tourSteps = this.runsComponent.tourSteps || [];
    }

    this.setState({ tourSteps: tourSteps });
  }

  handleShowNodeDialog() {
    this.setState({
      preview_text: JSON.stringify(this.node, null, 2),
    });
  }

  makeControls(plugins_info: any, kind: string | null, onUploadDialog: (descriptor: any) => void) {
    const items: any[] = [
      {
        render: makeControlToggles,
        props: {
          items: [
            {
              img: 'grid.svg',
              text: 'Graph',
              value: VIEW_MODE.GRAPH,
              enabled: this.state.is_graph,
            },
            {
              img: 'sliders.svg',
              text: 'Properties',
              value: VIEW_MODE.NODE,
            },
            {
              img: 'list.svg',
              text: 'Runs',
              value: VIEW_MODE.RUNS,
            },
          ],
          index: this.state.view_mode,
          onIndexChange: (view_mode: number | string) => this.handleSetViewMode(view_mode),
          key: 'key' + this.state.view_mode,
        },
      },

      {
        render: makeControlSeparator,
        props: { key: 'separator_1' },
      },

      {
        render: makeControlButton,
        props: {
          img: 'save.svg',
          text: 'Save',
          enabled: this.state.editable,
          func: () => this.handleSave(),
        },
      },
      {
        render: makeControlButton,
        props: {
          img: 'check-square.svg',
          text: 'Validate',
          enabled: this.state.editable,
          func: () => this.handleValidate(),
        },
      },
      {
        render: makeControlButton,
        props: {
          img: 'play.svg',
          text: 'Run',
          enabled: this.state.is_workflow && this.state.collection === COLLECTIONS.TEMPLATES,
          className: 'run-button',
          func: () => this.handleRun(),
        },
      },
      {
        render: makeControlButton,
        props: {
          img: 'check.svg',
          text: 'Approve',
          enabled: !this.state.is_workflow && this.state.editable,
          func: () => this.handleApprove(),
        },
      },
      {
        render: makeControlButton,
        props: {
          img: 'x.svg',
          text: 'Deprecate',
          enabled: !this.state.is_workflow && !this.state.editable,
          func: () => this.handleDeprecateClick(),
        },
      },
      {
        render: makeControlButton,
        props: {
          img: 'copy.svg',
          text: 'Clone',
          enabled: this.node && this.node.node_running_status !== NODE_RUNNING_STATUS.STATIC,
          func: () => this.handleClone(),
        },
      },
      {
        render: makeControlButton,
        props: {
          img: 'x.svg',
          text: 'Cancel',
          enabled: this.state.activeStatus,
          func: () => this.handleCancel(),
        },
      },
      {
        render: makeControlCheckbox,
        props: {
          text: 'Sync',
          enabled: this.state.editable && this.state.collection === COLLECTIONS.TEMPLATES,
          checked: this.state.node && this.state.node.auto_sync,
          visible: this.state.editable && this.state.collection === COLLECTIONS.TEMPLATES,
          func: (event: React.ChangeEvent<HTMLInputElement>) => this.handleChangeNodeParameter('auto_sync', event),
        },
      },
      {
        render: makeControlCheckbox,
        props: {
          text: 'Auto run',
          enabled: this.state.editable && this.state.collection === COLLECTIONS.TEMPLATES && this.state.is_workflow,
          checked: this.state.node && this.state.node.auto_run,
          visible: this.state.editable && this.state.collection === COLLECTIONS.TEMPLATES,
          func: (event: React.ChangeEvent<HTMLInputElement>) => this.handleChangeNodeParameter('auto_run', event),
        },
      },

      {
        render: makeControlSeparator,
        props: { key: 'separator_2' },
      },

      {
        render: makeControlButton,
        props: {
          img: 'trending-up.svg',
          text: 'Upgrade Nodes',
          enabled: this.state.is_graph && this.state.editable,
          func: () => this.handleUpgradeNodes(),
        },
      },
      {
        render: makeControlButton,
        props: {
          img: 'rearrange.svg',
          text: 'Auto layout',
          enabled: this.state.is_graph && this.state.editable,
          func: () => this.handleRearrangeNodes(),
        },
      },
      {
        render: makeControlButton,
        props: {
          img: 'preview.svg',
          text: 'Preview',
          enabled: !this.state.is_graph,
          className: 'preview-button',
          func: () => this.handlePreview(),
        },
      },
      {
        render: makeControlButton,
        props: {
          img: 'preview.svg',
          text: 'Json',
          enabled: true,
          className: 'show-code-button',
          func: () => this.handleShowNodeDialog(),
        },
      },
    ];

    if (kind && plugins_info?.workflows_dict?.[kind]) {
      try {
        items.push(
          ...plugins_info.workflows_dict[kind].static_operation_kinds
            .map((op_kind: string) => plugins_info.operations_dict[op_kind])
            .map((operation: any) => ({
              render: makeControlButton,
              props: {
                img: 'upload.svg',
                text: `Upload ${operation.title}`,
                func: () => {
                  onUploadDialog(plugins_info.operations_dict[operation.kind]);
                },
                enabled: this.state.is_workflow && this.state.editable,
                key: operation.kind,
              },
            }))
        );
      } catch (error) {
        console.log('Caught exception trying to render a button');
        console.log(error);
      }
    }

    items.push(
      ...[
        {
          render: makeControlSeparator,
          props: { key: 'separator_3' },
        },
        {
          render: makeControlButton,
          props: {
            img: 'info.svg',
            text: 'Show Tour',
            enabled: true,
            className: 'demo-button',
            func: () => this.handleTour(),
          },
        },
      ]
    );

    return makeControlPanel({
      props: {
        items: items,
        key: String(this.state.view_mode) + String(this.state.editable),
      },
    });
  }

  handleCloseUploadDialog() {
    this.setState({ uploadOperation: null });
  }

  render() {
    const node_running_status = this.state.node?.node_running_status ? this.state.node.node_running_status.toLowerCase() : '';
    return (
      <div className={`editor-view node-running-status-${node_running_status}`}>
        <PluginsProvider value={this.state.plugins_dict}>
          <AlertContainer ref={(a) => { this.msg = a; }} {...ALERT_OPTIONS} />
          {this.state.loading && <LoadingScreen />}
          {this.state.deprecateQuestionDialog && (
            <DeprecateDialog
              onClose={() => this.handleCloseDeprecateDialog()}
              prev_node_id={this.state.node._id}
              onDeprecate={(node_, action) => this.handleDeprecate(node_, action)}
              title={'Would you like to deprecate this Operation?'}
            />
          )}
          {this.state.deprecateParentDialog && (
            <DeprecateDialog
              onClose={() => this.handleCloseDeprecateDialog()}
              prev_node_id={this.state.node.parent_node_id}
              new_node_id={this.state.node._id}
              onDeprecate={(node_, action) => this.handleDeprecate(node_, action)}
              title={'Would you like to deprecate parent Operation?'}
            />
          )}
          {this.state.preview_text && (
            <TextViewDialog
              className="TextViewDialog"
              title="Preview"
              text={this.state.preview_text}
              showAlert={(message, type) => this.showAlert(message, type)}
              onClose={() => this.setState({ preview_text: null })}
            />
          )}
          <PluginsConsumer>
            {(plugins_info) =>
              this.makeControls(plugins_info, this.state.node ? this.state.node.kind : null, (operation_descriptor) => {
                console.log(operation_descriptor);
                this.setState({
                  uploadOperation: operation_descriptor,
                });
              })
            }
          </PluginsConsumer>
          <div className="editor-content">
            {this.state.view_mode === VIEW_MODE.GRAPH && (
              <ReactFlowProvider>
                <Graph
                  ref={(a) => { this.graphComponent = a; }}
                  node={this.state.node}
                  plugins_dict={this.state.plugins_dict}
                  onNodeChange={(node) => this.handleNodeChange(node)}
                  editable={this.state.editable}
                  showAlert={(message, type) => this.showAlert(message, type)}
                  onSave={() => this.handleSave()}
                  selectedNode={this.state.selectedNode}
                />
              </ReactFlowProvider>
            )}
            {this.state.view_mode === VIEW_MODE.NODE && (
              <Node
                ref={(a) => { this.nodeComponent = a; }}
                node={this.state.node}
                plugins_dict={this.state.plugins_dict}
                is_workflow={this.state.is_workflow}
                is_graph={this.state.is_graph}
                onNodeChange={(node) => this.handleNodeChange(node)}
                readOnly={!this.state.editable}
              />
            )}
            {this.state.view_mode === VIEW_MODE.RUNS && (
              <RunList
                ref={(a) => { this.runsComponent = a; }}
                showControlls={false}
                search={
                  'original_node_id:' +
                  (this.props.collection === COLLECTIONS.RUNS ? this.state.node.original_node_id : this.state.node._id)
                }
              />
            )}
            {this.state.uploadOperation && (
              <PluginsConsumer>
                {(plugins_info) => (
                  <FileUploadDialog
                    onClose={() => this.handleCloseUploadDialog()}
                    uploadOperation={this.state.uploadOperation}
                    plugins_info={plugins_info}
                    doNotSave
                    onUpload={(node) => this.graphComponent?.insertNode(node)}
                    showAlert={(message, type) => this.showAlert(message, type)}
                  />
                )}
              </PluginsConsumer>
            )}
          </div>
        </PluginsProvider>
        <Tour
          key={JSON.stringify(this.state.tourSteps)}
          steps={this.state.tourSteps}
          isOpen={this.state.tourSteps.length > 0}
          maskSpace={10}
          rounded={10}
          onRequestClose={() => {
            this.setState({ tourSteps: [] });
          }}
        />
      </div>
    );
  }
}
