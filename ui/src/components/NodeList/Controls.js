import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { GRAPH_RUNNING_STATUS } from '../../constants';
import { makeControlLink, makeControlToggles } from '../Common/controlButton';
import { VIEW_MODE } from '../Editor/index'

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

  constructor(props) {
    super(props);

    this.state = {
      index: 0,
    };
  }

  render() {
    const CREATE_BUTTONS = [
        {
            text: "Create BashJinja2",
            href: "/nodes/plynx.plugins.executors.local.BashJinja2",
        },
        {
            text: "Create PythonNode",
            href: "/nodes/plynx.plugins.executors.local.PythonNode",
        },
        {
            text: "Create Graph",
            href: "/nodes/plynx.plugins.executors.dag.DAG",
        },
    ];
    return (
      <div className={this.props.className + ' ' + (this.props.readonly ? 'readonly' : 'editable')}>
        { makeControlToggles ({
            items: [
                {
                  img: 'save.svg',
                  text: 'Graph',
                  value: VIEW_MODE.GRAPH,
              },
              {
                img: 'check-square.svg',
                text: 'Properties',
                value: VIEW_MODE.NODE,
              },
              {
                img: 'check-square.svg',
                text: 'Runs',
                value: VIEW_MODE.RUNS,
              },
            ],
          index: this.state.index,
          func: (view_mode) => this.props.onViewMode(view_mode),
          onIndexChange: (index) => this.setState({index: index}),
        })
        }
        {
          CREATE_BUTTONS.map((item) =>
              makeControlLink({
                img: 'plus.svg',
                text: item.text,
                href: item.href,
                key: item.text,
              })
          )
        }

      </div>
    );
  }
}
