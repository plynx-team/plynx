import React from 'react';
import PropTypes from 'prop-types';

class AlertMessage extends React.Component {
  constructor(props) {
    super(props);
    this.containerRef = React.createRef();
    this.timer = null;
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

    if (this.props.time > 0) {
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

AlertMessage.defaultProps = {
  icon: '',
  message: '',
  type: 'info',
  time: 5000,
};

AlertMessage.propTypes = {
  uniqueKey: PropTypes.string,
  icon: PropTypes.node,
  message: PropTypes.node,
  style: PropTypes.object,
  closeIconClass: PropTypes.string,
  time: PropTypes.number,
  type: PropTypes.oneOf(['info', 'success', 'error']),
  onRemove: PropTypes.func,
};

export default AlertMessage;
