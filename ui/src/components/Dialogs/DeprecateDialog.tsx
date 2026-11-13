import React, { Component, ChangeEvent } from 'react';
import { Link } from 'react-router-dom';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Dialog from './Dialog';
import NodeItem from '../Common/NodeItem';
import { PLynxApi } from '../../api';
import { ACTION, COLLECTIONS } from '../../constants';
import { NodeData } from '../../types';

import './DeprecateDialog.css';

export interface DeprecateDialogProps {
  title: string;
  new_node?: NodeData | null;
  prev_node?: NodeData | null;
  new_node_id?: string;
  prev_node_id?: string;
  onCancel?: () => void;
  onClose: () => void;
  onDeprecate: (node: NodeData, action: string) => void;
  onNo?: boolean;
}

interface DeprecateDialogState {
  prev_node: NodeData | null | undefined;
  prev_node_loading: boolean;
  prev_node_id: string;
  new_node: NodeData | null | undefined;
  new_node_loading: boolean;
  new_node_id: string;
}

export default class DeprecateDialog extends Component<DeprecateDialogProps, DeprecateDialogState> {
  constructor(props: DeprecateDialogProps) {
    super(props);

    let prevNodeLoading = false;
    let newNodeLoading = false;
    let prevNodeId = '';
    let newNodeId = '';

    if (!this.props.prev_node && this.props.prev_node_id) {
      this.updateNode(this.props.prev_node_id, 'prev_node');
      prevNodeLoading = true;
      prevNodeId = this.props.prev_node_id;
    } else if (this.props.prev_node) {
      prevNodeId = this.props.prev_node._id;
    }

    if (!this.props.new_node && this.props.new_node_id) {
      this.updateNode(this.props.new_node_id, 'new_node');
      newNodeLoading = true;
      newNodeId = this.props.new_node_id;
    } else if (this.props.new_node) {
      newNodeId = this.props.new_node._id;
    }

    this.state = {
      prev_node: this.props.prev_node,
      prev_node_loading: prevNodeLoading,
      prev_node_id: prevNodeId,
      new_node: this.props.new_node,
      new_node_loading: newNodeLoading,
      new_node_id: newNodeId,
    };
  }

  updateNode(nodeId: string, destination: 'prev_node' | 'new_node', retryCount = 3) {
    PLynxApi.endpoints[COLLECTIONS.TEMPLATES].getOne({ id: nodeId })
      .then((response: any) => {
        const node = response.data.node;
        this.setState({
          [destination]: node,
          [`${destination}_id`]: node._id,
          [`${destination}_loading`]: false,
        } as any);
      })
      .catch((error: any) => {
        console.error(error);
        if (error.response && error.response.status === 404) {
          this.setState({ [`${destination}_loading`]: false } as any);
        }
        if (error.response && error.response.status === 401) {
          PLynxApi.getAccessToken().then((isSuccessfull) => {
            if (!isSuccessfull) {
              this.setState({ [`${destination}_loading`]: false } as any);
            } else if (retryCount > 0) {
              this.updateNode(nodeId, destination, retryCount - 1);
              this.setState({ [`${destination}_loading`]: true } as any);
            } else {
              this.setState({ [`${destination}_loading`]: false } as any);
            }
          });
        }
      });
  }

  handleDeprecate(mode: 'optionally' | 'mandatory') {
    const node = this.state.prev_node;
    if (!node) return;
    const newNode = this.state.new_node;
    if (newNode) {
      node.successor_node_id = newNode._id;
    }
    if (mode === 'optionally') {
      this.props.onDeprecate(node, ACTION.DEPRECATE);
    } else if (mode === 'mandatory') {
      this.props.onDeprecate(node, ACTION.MANDATORY_DEPRECATE);
    }

    this.props.onClose();
  }

  handleCancel() {
    if (this.props.onNo && this.props.onCancel) {
      this.props.onCancel();
    }
    this.props.onClose();
  }

  handleNewNodeIdChange(event: ChangeEvent<HTMLInputElement>) {
    const val = event.target.value;
    this.setState({ new_node_id: val });
    if (val.length === 24) {
      this.updateNode(val, 'new_node');
      this.setState({
        new_node_loading: true,
      });
    } else {
      this.setState({
        new_node: null,
        new_node_loading: false,
      });
    }
  }

  render() {
    return (
      <Dialog
        className="DeprecateDialogWindow"
        onClose={() => {
          this.props.onClose();
        }}
        width={600}
        height={250}
        title="Deprecation"
        enableResizing={false}
      >
        <div className="DeprecateDialog">
          <div className="MainBlock">
            <div className="Title">{this.props.title}</div>

            <hr />

            <div className="Row">
              <div className="Col">
                <div>Id:</div>
                <Link to={`/${COLLECTIONS.TEMPLATES}/${this.state.prev_node_id}`}>
                  {this.state.prev_node_id}{' '}
                  <img src="/icons/external-link.svg" width="12" height="12" alt="link" />
                </Link>
              </div>

              <div className="Divider" />

              <div className="Col">
                <div>Id:</div>
                <input
                  className="Cell"
                  type="text"
                  onChange={(event) => this.handleNewNodeIdChange(event)}
                  value={this.state.new_node_id}
                />
              </div>
            </div>

            <div className="Row">
              <div className="Prev">
                {this.state.prev_node && <NodeItem node={this.state.prev_node} />}
                {this.state.prev_node_loading && 'Loading...'}
                {!this.state.prev_node && !this.state.prev_node_loading && 'Not found'}
              </div>

              <div className="Divider">
                <img src="/icons/chevron-right-2x.png" className="arrow" alt="arrow" />
              </div>

              <div className="New">
                {this.state.new_node && <NodeItem node={this.state.new_node} />}
                {this.state.new_node_loading && 'Loading...'}
                {!this.state.new_node && !this.state.new_node_loading && 'Not found'}
              </div>
            </div>
          </div>

          <Stack direction="row" spacing={1.5} justifyContent="flex-end" sx={{ marginTop: 2 }}>
            <Button
              variant="outlined"
              color="warning"
              size="small"
              startIcon={<img src="/icons/alert-circle.svg" alt="deprecate" width="16" height="16" />}
              onClick={(e) => {
                e.preventDefault();
                this.handleDeprecate('optionally');
              }}
              sx={{ textTransform: 'none' }}
            >
              Deprecate (optionally)
            </Button>
            <Button
              variant="contained"
              color="error"
              size="small"
              startIcon={<img src="/icons/alert-octagon.svg" alt="deprecate" width="16" height="16" />}
              onClick={(e) => {
                e.preventDefault();
                this.handleDeprecate('mandatory');
              }}
              sx={{ textTransform: 'none' }}
            >
              Deprecate (mandatory)
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              size="small"
              startIcon={<img src="/icons/x.svg" alt="cancel" width="16" height="16" />}
              onClick={(e) => {
                e.preventDefault();
                this.handleCancel();
              }}
              sx={{ textTransform: 'none', borderColor: '#555' }}
            >
              Cancel
            </Button>
          </Stack>
        </div>
      </Dialog>
    );
  }
}
