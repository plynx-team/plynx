import React, { Component, ReactNode, MouseEvent } from 'react';
import { Rnd } from 'react-rnd';

import './Dialog.css';

export interface DialogProps {
  children: ReactNode;
  enableResizing?: boolean;
  height?: number;
  onClose: () => void;
  title: string;
  width: number;
  className?: string;
  defaultX?: number;
  defaultY?: number;
}

interface DialogState {
  width: number;
  height?: number;
}

export default class Dialog extends Component<DialogProps, DialogState> {
  x: number = -100;
  y: number = -100;

  constructor(props: DialogProps) {
    super(props);

    this.state = {
      width: this.props.width,
      height: this.props.height,
    };
  }

  handleClose(e: MouseEvent<any>) {
    this.noop(e);
    this.props.onClose();
  }

  handleBackgroundMouseDown(e: MouseEvent<HTMLDivElement>) {
    this.x = e.screenX;
    this.y = e.screenY;
  }

  handleBackgroundMouseUp(e: MouseEvent<HTMLDivElement>) {
    if ((this.x - e.screenX) ** 2 + (this.y - e.screenY) ** 2 < 25) {
      this.handleClose(e);
    }
    this.x = -1;
    this.y = -1;
  }

  noop(e: any) {
    if (e && e.stopPropagation) {
      e.stopPropagation();
    }
  }

  render() {
    let x = (window.innerWidth - this.props.width) / 2;
    let y = (window.innerHeight - (this.props.height || 400)) / 2;
    if (this.props.defaultX !== undefined) {
      x = Math.min(this.props.defaultX, window.innerWidth - this.props.width);
    }
    if (this.props.defaultY !== undefined) {
      y = Math.min(this.props.defaultY, window.innerHeight - (this.props.height || 400));
    }

    return (
      <div
        className="dialog noselect"
        onMouseDown={(e) => this.handleBackgroundMouseDown(e)}
        onMouseUp={(e) => this.handleBackgroundMouseUp(e)}
      >
        <Rnd
          className="dialog-rnd"
          default={{
            x,
            y,
            width: this.props.width + 2,
            height: this.props.height ? this.props.height + 2 : 'auto',
          }}
          minWidth={200}
          minHeight={100}
          onResize={(_e, _direction, ref, _delta, position) => {
            this.setState({
              width: ref.offsetWidth,
              height: ref.offsetHeight,
              ...position,
            });
          }}
          onClick={(e) => this.noop(e)}
          onMouseUp={(e) => this.noop(e)}
          enableResizing={this.props.enableResizing}
          bounds="parent"
        >
          <div className="dialog-window">
            <div
              className="header"
              onClick={(e) => this.noop(e)}
              onMouseUp={(e) => this.noop(e)}
            >
              <div
                className="close-button"
                onClick={(e) => this.handleClose(e)}
              >
                &#215;
              </div>
              <div
                className="title noselect"
                onClick={(e) => {
                  this.noop(e);
                }}
              >
                {this.props.title}
              </div>
            </div>
            <div
              className={`content ${this.props.className || ''}`.trim()}
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
