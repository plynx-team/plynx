import React from 'react';
import PropTypes from 'prop-types';
import onClickOutside from 'react-onclickoutside';

import TrashIcon from './TrashIcon';


class Spline extends React.Component {
  static propTypes = {
    color: PropTypes.string.isRequired,
    start: PropTypes.shape({
      x: PropTypes.number.isRequired,
      y: PropTypes.number.isRequired,
    }).isRequired,
    end: PropTypes.shape({
      x: PropTypes.number.isRequired,
      y: PropTypes.number.isRequired,
    }).isRequired,
    mousePos: PropTypes.shape({
      x: PropTypes.number.isRequired,
      y: PropTypes.number.isRequired,
    }),
    onClick: PropTypes.func,
    onClickOutside: PropTypes.func,
    onDeselected: PropTypes.func,
    onRemove: PropTypes.func,
    onSelected: PropTypes.func,
    readonly: PropTypes.bool.isRequired,
  }

  constructor(props) {
    super(props);
    this.state = {
      selected: false,
      position: { x: 0, y: 0 }
    };
  }

  handleClick(e) {
    if (this.props.readonly) {
      return;
    }
    this.setState({
      selected: !this.state.selected,
      position: this.props.mousePos
    }, () => {
      if (this.props.onSelected && this.state.selected) {
        this.props.onSelected(e);
      } else if (this.props.onDeselected && !this.state.selected) {
        this.props.onDeselected(e);
      }
    });

    if (this.props.onClick) {
      this.props.onClick(e);
    }
  }

  handleClickOutside(e) {
    this.setState({selected: false});

    if (this.props.onClickOutside) {
      this.props.onClickOutside(e);
    }
    if (this.props.onDeselected) {
      this.props.onDeselected(e);
    }
  }

  handleRemove(e) {
    this.setState({selected: false});

    if (this.props.onRemove) {
      this.props.onRemove(e);
    }
  }

  render() {
    const {selected, position} = this.state;

    const {start, end} = this.props;

    const dist = this.distance([start.x, start.y], [end.x, end.y]);

    const pathString = this.bezierCurve(start.x,                    // start x
                                          start.y,                  // start y
                                          start.x + (dist * 0.25),  // cp1 x
                                          start.y,                  // cp1 y
                                          end.x - (dist * 0.25),    // cp2 x
                                          end.y,                    // cp2 y
                                          end.x,                    // end x
                                          end.y);                   // end y

    const className = 'connector' + (selected ? ' selected' : '');
    const color = "#" + this.props.color;
    const style = {
      stroke: color,
      strokeWidth: selected ? 8 : 5,
    };

    return (
                <g>
                <circle cx={start.x - 0.4} cy={start.y} r="4" fill={color} />
                <circle cx={end.x} cy={end.y} r="4" fill="#9191A8" />
                <path className="connector-click-area" d={pathString} onClick={(e) => {
                  this.handleClick(e);
                }} />
                <path className={className} d={pathString} onClick={(e) => {
                  this.handleClick(e);
                }} style={style}/>
                { selected ?
                    <TrashIcon position={position}
                               onClick={(e) => {
                                 this.handleRemove(e);
                               }}
                               color={color}
                    />
                : null }
                </g>


    );
  }

  bezierCurve(a, b, cp1x, cp1y, cp2x, cp2y, x, y) {
    return `M${a},${b} C${cp1x},${cp1y} ${cp2x},${cp2y}  ${x},${y}`;
  }

  distance(a, b) {
    return Math.sqrt(((b[0] - a[0]) * (b[0] - a[0])) + ((b[1] - a[1]) * (b[1] - a[1])));
  }
}

export default onClickOutside(Spline);
