import React, { Component, ReactNode, CSSProperties, createRef } from 'react';

export interface AlertMessageStyle {
  alert?: CSSProperties;
  closeButton?: {
    bg?: string;
  };
}

export interface AlertMessageProps {
  uniqueKey?: string;
  icon?: ReactNode;
  message?: ReactNode;
  style?: AlertMessageStyle;
  closeIconClass?: string;
  time?: number;
  type?: 'info' | 'success' | 'error' | string;
  onRemove?: (key?: string) => void;
}

interface AlertMessageState {
  closeButtonStyle: CSSProperties;
}

export default class AlertMessage extends Component<AlertMessageProps, AlertMessageState> {
  static defaultProps = {
    icon: '',
    message: '',
    type: 'info',
    time: 5000,
  };

  private containerRef = createRef<HTMLDivElement>();
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(props: AlertMessageProps) {
    super(props);
    this.state = {
      closeButtonStyle: {
        backgroundColor: props.style?.closeButton?.bg,
      },
    };
  }

  componentDidMount() {
    const node = this.containerRef.current;
    if (node) {
      this.setState({
        closeButtonStyle: {
          height: `${node.offsetHeight}px`,
          lineHeight: `${node.offsetHeight}px`,
          backgroundColor: this.props.style?.closeButton?.bg,
        },
      });
    }

    if (this.props.time && this.props.time > 0) {
      this.timer = setTimeout(() => {
        this._removeSelf();
      }, this.props.time);
    }
  }

  componentWillUnmount() {
    if (this.timer) {
      clearTimeout(this.timer);
    }
  }

  _removeSelf() {
    if (this.props.onRemove) {
      this.props.onRemove(this.props.uniqueKey);
    }
  }

  _showIcon() {
    if (this.props.icon) {
      return this.props.icon;
    }
    return <div className={`${this.props.type}-icon`} />;
  }

  render() {
    const className = ['alert', this.props.type].filter(Boolean).join(' ');
    return (
      <div ref={this.containerRef} style={this.props.style?.alert} className={className}>
        <div className="content icon">
          {this._showIcon()}
        </div>
        <div className="content message">
          {this.props.message}
        </div>
        <div onClick={() => this._removeSelf()} style={this.state.closeButtonStyle} className="content close">
          <div className={this.props.closeIconClass} />
        </div>
      </div>
    );
  }
}
