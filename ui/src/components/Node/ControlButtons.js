import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { NODE_STATUS } from '../../constants';
import { makeControlButton } from '../Common/controlButton';

export default class ControlButtons extends Component {
  constructor(props) {
    super(props);
    this.state = {
      readOnly: props.readOnly
    };
  }

  handleSave() {
    this.props.onSave();
  }

  handleSaveApprove() {
    this.props.onSaveApprove();
  }

  handleClone() {
    this.props.onClone();
  }

  handleDeprecate() {
    this.props.onDeprecate();
  }

  render() {
    return (
      <div className="ControlButtons">
        {!this.state.readOnly &&
          makeControlButton({
            img: 'save.svg',
            text: 'Save',
            func: () => {
              this.props.onSave();
            },
          })

        }
        {!this.state.readOnly &&
          makeControlButton({
            img: 'play.svg',
            className: 'demo',
            text: 'Approve',
            func: () => {
              this.props.onSaveApprove();
            },
          })
        }
        {(!this.props.hideDeprecate && this.props.nodeStatus === NODE_STATUS.READY) &&
            makeControlButton({
              img: 'x.svg',
              text: 'Deprecate',
              func: () => {
                this.props.onDeprecate();
              },
            })
        }
        {makeControlButton({
          img: 'preview.svg',
          text: 'Preview',
          func: () => {
            this.props.onPreview();
          },
        })}

        {makeControlButton({
          img: 'copy.svg',
          text: 'Clone',
          func: () => {
            this.props.onClone();
          },
        })}
      </div>
    );
  }
}

ControlButtons.propTypes = {
  readOnly: PropTypes.bool,
  nodeStatus: PropTypes.oneOf(Object.values(NODE_STATUS)),
  hideDeprecate: PropTypes.bool,
  onClone: PropTypes.func,
  onDeprecate: PropTypes.func,
  onPreview: PropTypes.func,
  onSave: PropTypes.func,
  onSaveApprove: PropTypes.func,
};
