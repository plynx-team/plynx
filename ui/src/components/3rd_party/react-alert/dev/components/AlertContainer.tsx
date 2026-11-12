import React, { Component, CSSProperties, ReactNode } from 'react';
import AlertMessage, { AlertMessageStyle } from './AlertMessage';

export interface AlertOptions {
  type?: string;
  time?: number;
  icon?: ReactNode;
  [key: string]: unknown;
}

export interface AlertItem extends AlertOptions {
  message: ReactNode;
  uniqueKey: string;
  style: AlertMessageStyle;
  closeIconClass: string;
}

export interface AlertContainerProps {
  offset?: number;
  position?: 'bottom left' | 'bottom right' | 'top right' | 'top left' | string;
  theme?: 'dark' | 'light' | string;
  time?: number;
  transition?: 'scale' | 'fade' | string;
}

interface AlertContainerState {
  alerts: AlertItem[];
}

export default class AlertContainer extends Component<AlertContainerProps, AlertContainerState> {
  static defaultProps: AlertContainerProps = {
    offset: 14,
    position: 'bottom left',
    theme: 'dark',
    time: 5000,
    transition: 'scale',
  };

  constructor(props: AlertContainerProps) {
    super(props);
    this.state = {
      alerts: [],
    };
  }

  success(message: ReactNode, options: AlertOptions = {}) {
    this.show(message, { ...options, type: 'success' });
  }

  error(message: ReactNode, options: AlertOptions = {}) {
    this.show(message, { ...options, type: 'error' });
  }

  info(message: ReactNode, options: AlertOptions = {}) {
    this.show(message, { ...options, type: 'info' });
  }

  show(message: ReactNode, options: AlertOptions = {}) {
    const alert: AlertItem = {
      message,
      ...options,
      uniqueKey: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      style: this._getTheme(),
      time: Object.prototype.hasOwnProperty.call(options, 'time') ? options.time : this.props.time,
      closeIconClass: `close-${this.props.theme}`,
    };
    this.setState((prev) => ({ alerts: [...prev.alerts, alert] }));
  }

  removeAll() {
    this.setState({ alerts: [] });
  }

  _handleRemove = (uniqueKey?: string) => {
    this.setState((prev) => ({
      alerts: prev.alerts.filter((a) => a.uniqueKey !== uniqueKey),
    }));
  };

  _getStyle(): CSSProperties {
    let position: CSSProperties;
    switch (this.props.position) {
      case 'top left':
        position = { top: 0, right: 'auto', bottom: 'auto', left: 0 };
        break;
      case 'top right':
        position = { top: 0, right: 0, bottom: 'auto', left: 'auto' };
        break;
      case 'bottom left':
        position = { top: 'auto', right: 'auto', bottom: 0, left: 0 };
        break;
      default:
        position = { top: 'auto', right: 0, bottom: 0, left: 'auto' };
        break;
    }

    return {
      margin: `${this.props.offset}px`,
      ...position,
    };
  }

  _getTheme(): AlertMessageStyle {
    if (this.props.theme === 'light') {
      return {
        alert: { backgroundColor: '#fff', color: '#333' },
        closeButton: { bg: '#f3f3f3' },
      };
    }
    return {
      alert: { backgroundColor: '#333', color: '#fff' },
      closeButton: { bg: '#444' },
    };
  }

  render() {
    return (
      <div style={this._getStyle()} className="react-alerts">
        <div>
          {this.state.alerts.map((alert) => (
            <AlertMessage
              key={alert.uniqueKey}
              {...alert}
              onRemove={this._handleRemove}
            />
          ))}
        </div>
      </div>
    );
  }
}
