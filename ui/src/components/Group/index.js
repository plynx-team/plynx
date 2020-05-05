import React, { Component } from 'react';
import Tour from 'reactour';
import PropTypes from 'prop-types';
import DirectoryColumn from './DirectoryColumn';
import queryString from 'query-string';
import AlertContainer from '../3rd_party/react-alert';
import { PLynxApi } from '../../API';
import cookie from 'react-cookies';
import LoadingScreen from '../LoadingScreen';
import {
  ACTION,
  RELOAD_OPTIONS,
  RESPONCE_STATUS,
  ALERT_OPTIONS,
  VALIDATION_CODES,
  VALIDATION_TARGET_TYPE,
  NODE_STATUS,
  COLLECTIONS,
  ACTIVE_NODE_RUNNING_STATUSES,
} from '../../constants';
import HubPanel from '../Graph/HubPanel';
import RunList from '../NodeList/runList';
import DeprecateDialog from '../Dialogs/DeprecateDialog';
import TextViewDialog from '../Dialogs/TextViewDialog';
import { PluginsProvider } from '../../contexts';
import { makeControlPanel, makeControlToggles, makeControlButton, makeControlSeparator } from '../Common/controlButton';
import { addStyleToTourSteps } from '../../utils';
import "./style.css";


export const VIEW_MODE = Object.freeze({
  NONE: 'none',
  GRAPH: 0,
  NODE: 1,
  RUNS: 2,
});


const FIRST_TIME_APPROVED_STATE = 'first_time_approved_state';
const UPDATE_TIMEOUT = 1000;


export default class Editor extends Component {
  static propTypes = {
    history: PropTypes.object.isRequired,
    location: PropTypes.object.isRequired,
    collection: PropTypes.string.isRequired,
    match: PropTypes.shape({
      params: PropTypes.shape({
        group_id: PropTypes.string,
      }),
    }),
  }

  constructor(props) {
    super(props);

    this.state = {
      editable: true,
      loading: true,
      view_mode: VIEW_MODE.NONE,
      deprecateQuestionDialog: false,
      deprecateParentDialog: false,
      collection: null,
      tourSteps: [],
      activeStatus: false,
    };

    let token = cookie.load('refresh_token');
    // TODO remove after demo
    if (token === 'Not assigned') {
      token = cookie.load('access_token');
    }

    this.tour_steps = [];
    console.log(global.appVersion);
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async componentDidMount() {
    // Loading

    const self = this;
    let loading = true;
    const group_id = this.props.match.params.group_id.replace(/\$+$/, '');
    let sleepPeriod = 1000;
    const sleepMaxPeriod = 10000;
    const sleepStep = 1000;

    const loadNode = (response) => {
      const searchValues = queryString.parse(this.props.location.search);
      let group = response.data.group;
      self.group = group;
      console.log('group', group);

      self.setState({
        plugins_dict: response.data.plugins_dict,
        group: self.group,
      });

      console.log('group_id:', group_id);
      if (!group_id.startsWith(self.group._id)) {
        self.props.history.replace("/" + self.props.collection + "/" + self.group._id + '$');
      }

      loading = false;
    };

    const handleError = (error) => {
      console.error(error);
      console.error('-----------');
      if (!error.response) {
        self.setState({error_message: error});
      } else if (error.response.status === 404) {
        self.props.history.replace("/not_found");
        window.location.reload(false);
        loading = false;
      } else if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            window.location = '/login';
          } else {
            self.showAlert('Updated access token', 'success');
          }
        });
      }
    };

    /* eslint-disable no-await-in-loop */
    /* eslint-disable no-unmodified-loop-condition */
    while (loading) {
      await PLynxApi.endpoints[self.props.collection].getOne({ id: group_id})
      .then(loadNode)
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

  componentWillUnmount() {
    if (this.timeout) {
      clearTimeout(this.timeout);
    }
  }

  postGroup({group, reloadOption, action, retryOnAuth = true} = {}) {
    /* action might be in {'save', 'validate', 'approve', 'deprecate'}*/
    const self = this;
    self.setState({loading: true});

    console.log(action, group);


    PLynxApi.endpoints.groups
    .create({
      group: group,
      action: action
    })
    .then((response) => {
      const data = response.data;
      console.log('response', data);
      self.setState({loading: false});
      if (data.status === RESPONCE_STATUS.SUCCESS) {
        if (reloadOption === RELOAD_OPTIONS.OPEN_NEW_LINK) {
          this.props.history.push(response.data.url);
        }

        if (action === ACTION.SAVE) {
          self.showAlert("Saved", 'success');
        }
      } else {
        console.warn(data.message);
        self.showAlert(data.message, 'failed');
      }
    })
    .catch((error) => {
      console.log(error);
      if (error.response.status === 401) {
        PLynxApi.getAccessToken()
        .then((isSuccessfull) => {
          if (!isSuccessfull) {
            console.error("Could not refresh token");
            self.showAlert('Failed to authenticate', 'failed');
          } else if (retryOnAuth) {
                // Token updated, try posting again
            self.postGroup({group: group, reloadOption: reloadOption, action: action, retryOnAuth: false});
          } else {
            self.showAlert('Failed to save the graph, please try again', 'failed');
          }
        });
      } else {
        try {
          self.showAlert(error.response.data.message, 'failed');
        } catch {
          self.showAlert('Unknown error', 'failed');
        }
      }
      self.setState({loading: false});
    });
  }

  showAlert(message, type) {
    this.msg.show(message, {
      time: 5000,
      type: 'error',
      icon: <img src={"/alerts/" + type + ".svg"} width="32" height="32" alt="alert"/>
    });
  }

  handleNodeChange(node) {
    this.node = node;
  }

  handleSave() {
    console.log('to_save', this.group);
    this.postGroup({
      group: this.group,
      action: ACTION.SAVE,
      reloadOption: RELOAD_OPTIONS.NONE,
    });
  }


  handleTour() {
    this.setState({tourSteps: []});
  }

  makeControls() {
    const items = [
      {
        render: makeControlButton,
        props: {
          img: 'save.svg',
          text: 'Save',
          enabled: this.state.editable,
          func: () => this.handleSave(),
        },
      }
    ];

    return makeControlPanel(
      {
        props: {
          items: items,
          key: this.state.view_mode + this.state.editable,
        },
      });
  }

  render() {
    return (
        <div
          className={`group-view`}
        >
          <PluginsProvider value={this.state.plugins_dict}>
              <AlertContainer ref={a => this.msg = a} {...ALERT_OPTIONS} />
              {this.state.loading &&
                <LoadingScreen
                ></LoadingScreen>
              }
              {this.makeControls()}
              {this.state.group &&
                  <div>
                    <pre>
                    {this.state.group._id}
                    </pre>
                    <DirectoryColumn items={this.state.group.items} />
                  </div>
              }
          </PluginsProvider>
          <Tour
              key={this.state.tourSteps}
              steps={this.state.tourSteps}
              isOpen={this.state.tourSteps.length > 0}
              maskSpace={10}
              rounded={10}
              onRequestClose={() => {
                this.setState({tourSteps: []});
              }}
          />
        </div>
    );
  }
}
