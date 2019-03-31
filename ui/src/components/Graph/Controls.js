import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { GRAPH_RUNNING_STATUS } from '../../constants';
import makeControlButton from '../Common/controlButton';
import './OutputItem.css';


export default class Controls extends Component {
  static propTypes = {
    className: PropTypes.string.isRequired,
    graphRunningStatus: PropTypes.oneOf(Object.values(GRAPH_RUNNING_STATUS)),
    onApprove: PropTypes.func.isRequired,
    onCancel: PropTypes.func.isRequired,
    onClone: PropTypes.func.isRequired,
    onGenerateCode: PropTypes.func.isRequired,
    onRearrange: PropTypes.func.isRequired,
    onSave: PropTypes.func.isRequired,
    onUpgradeNodes: PropTypes.func.isRequired,
    onValidate: PropTypes.func.isRequired,
    readonly: PropTypes.bool.isRequired,
  }

  render() {
    return (
      <div className={this.props.className + ' ' + (this.props.readonly ? 'readonly' : 'editable')}>
        {!this.props.readonly &&
          makeControlButton({
            img: 'save.svg',
            text: 'Save',
            func: () => {
              this.props.onSave();
            },
          })
        }
        {!this.props.readonly &&
          makeControlButton({
            img: 'check-square.svg',
            text: 'Validate',
            func: () => {
              this.props.onValidate();
            },
          })
        }
        {!this.props.readonly &&
          makeControlButton({
            img: 'play.svg',
            text: 'Run',
            func: () => {
              this.props.onApprove();
            },
          })
        }
        {!this.props.readonly &&
          makeControlButton({
            img: 'trending-up.svg',
            text: 'Upgrade Nodes',
            func: () => {
              this.props.onUpgradeNodes();
            },
          })
        }
        {makeControlButton({
          img: 'rearrange.svg',
          text: 'Rearrange nodes',
          func: () => {
            this.props.onRearrange();
          },
        })}
        {makeControlButton({
          img: 'preview.svg',
          text: 'API',
          func: () => {
            this.props.onGenerateCode();
          },
        })}
        {makeControlButton({
          img: 'copy.svg',
          text: 'Clone',
          func: () => {
            this.props.onClone();
          },
        })}
        {(this.props.graphRunningStatus === GRAPH_RUNNING_STATUS.RUNNING || this.props.graphRunningStatus === GRAPH_RUNNING_STATUS.FAILED_WAITING) &&
          makeControlButton({
            img: 'x.svg',
            text: 'Cancel',
            func: () => {
              this.props.onCancel();
            },
          })
        }
      </div>
    );
  }
}
