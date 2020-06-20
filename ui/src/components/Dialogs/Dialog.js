import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Rnd } from 'react-rnd';

import './Dialog.css';

export default class Dialog extends Component {
  static propTypes = {
    children: PropTypes.oneOfType([
      PropTypes.array.isRequired,
      PropTypes.object.isRequired,
    ]),
    enableResizing: PropTypes.bool.isRequired,
    height: PropTypes.number.isRequired,
    onClose: PropTypes.func.isRequired,
    title: PropTypes.string.isRequired,
    width: PropTypes.number.isRequired,
    className: PropTypes.string.isRequired,
  }

  constructor(props) {
    super(props);

    this.state = {
      width: this.props.width,
      height: this.props.height
    };

    this.x = -100;
    this.y = -100;
  }

  handleClose(e) {
    this.noop(e);
    this.props.onClose();
  }

  handleBackgroundMouseDown(e) {
    this.x = e.screenX;
    this.y = e.screenY;
  }

  handleBackgroundMouseUp(e) {
    if (((this.x - e.screenX) ** 2) + ((this.y - e.screenY) ** 2) < 25) {
      this.handleClose(e);
    }
    this.x = -1;
    this.y = -1;
  }

  noop(e) {
    e.stopPropagation();
  }

  render() {
    return (
      <div className='dialog noselect'
           onMouseDown={(e) => this.handleBackgroundMouseDown(e)}
           onMouseUp={(e) => this.handleBackgroundMouseUp(e)}
      >
        <Rnd
          className='dialog-rnd'
          default={{
            x: (window.innerWidth - this.props.width) / 2,
            y: (window.innerHeight - this.props.height) / 2,
            width: this.props.width,
            height: this.props.height,
          }}
          minWidth={400}
          minHeight={100}
          onResize={(e, direction, ref, delta, position) => {
            this.setState({
              width: ref.offsetWidth,
              height: ref.offsetHeight,
              ...position,
            });
          }}
          onClick={(e) => this.noop(e)}
          onMouseUp={(e) => this.noop(e)}
          enableResizing={this.props.enableResizing}
          bounds='parent'
        >
          <div className='dialog-window'
          >
            <div className='header'
              onClick={(e) => this.noop(e)}
              onMouseUp={(e) => this.noop(e)}
            >
              <div className="close-button"
                 onClick={(e) => this.handleClose(e)}
              >
                &#215;
              </div>
              <div className='title noselect'
                   onClick={(e) => {
                     this.noop(e);
                   }}
              >
                {this.props.title}
              </div>
            </div>
            <div className={'content ' + this.props.className}
                 onClick={(e) => {
                   this.noop(e);
                 }}
                 onMouseDown={(e) => {
                   this.noop(e);
                 }}
            >
              {this.props.children}
            </div>
          </div>
        </Rnd>
      </div>
    );
  }
}
