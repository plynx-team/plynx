import React from 'react';
import PropTypes from 'prop-types';
import AlertMessage from './AlertMessage';

class AlertContainer extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      alerts: [],
    };
  }

  success(message, options = {}) {
    this.show(message, { ...options, type: 'success' });
  }

  error(message, options = {}) {
    this.show(message, { ...options, type: 'error' });
  }

  info(message, options = {}) {
    this.show(message, { ...options, type: 'info' });
  }

  show(message, options = {}) {
    const alert = {
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

  _handleRemove = (uniqueKey) => {
    this.setState((prev) => ({
      alerts: prev.alerts.filter((a) => a.uniqueKey !== uniqueKey),
    }));
  };

  _getStyle() {
    let position;
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

  _getTheme() {
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

AlertContainer.defaultProps = {
  offset: 14,
  position: 'bottom left',
  theme: 'dark',
  time: 5000,
  transition: 'scale',
};

AlertContainer.propTypes = {
  offset: PropTypes.number,
  position: PropTypes.oneOf([
    'bottom left',
    'bottom right',
    'top right',
    'top left',
  ]),
  theme: PropTypes.oneOf(['dark', 'light']),
  time: PropTypes.number,
  transition: PropTypes.oneOf(['scale', 'fade']),
};

export default AlertContainer;
