import React, { Component, ChangeEvent } from 'react';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import Icon from '../Common/Icon';
import { PluginsConsumer } from '../../contexts';
import OutputItem from '../Graph/OutputItem';
import { PreviewData, PluginsDict } from '../../types';

export interface InOutItemData {
  name: string;
  file_type: string;
  is_array?: boolean;
  min_count?: number;
  values?: any[];
  _key?: string;
  [key: string]: any;
}

export interface InOutItemProps {
  index: number;
  readOnly?: boolean;
  name?: string;
  onChanged?: (index: number, name: string, value: any) => void;
  onRemove?: (index: number) => void;
  item: InOutItemData;
  nodeKind: string;
  onPreview: (previewData: PreviewData) => void;
  _key?: string;
}

interface InOutItemState {
  item: InOutItemData;
  index: number;
  readOnly?: boolean;
  remove_hover?: boolean;
}

export default class InOutItem extends Component<InOutItemProps, InOutItemState> {
  item: InOutItemData;

  constructor(props: InOutItemProps) {
    super(props);
    this.item = { ...this.props.item };
    this.state = {
      item: this.item,
      index: this.props.index,
      readOnly: this.props.readOnly,
      remove_hover: false,
    };

    this.handleChange = this.handleChange.bind(this);
  }

  componentDidUpdate(prevProps: InOutItemProps) {
    if (prevProps.item !== this.props.item || prevProps.readOnly !== this.props.readOnly) {
      this.item = { ...this.props.item };
      this.setState({
        item: this.item,
        readOnly: this.props.readOnly,
      });
    }
  }

  handleChange(event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    if (this.state.readOnly) {
      return;
    }
    const name = event.target.name;
    const value =
      event.target.type === 'checkbox'
        ? (event.target as HTMLInputElement).checked
        : event.target.value;
    this.item[name] = value;
    this.setState({ item: this.item });
    if (this.props.onChanged) {
      this.props.onChanged(this.props.index, name, value);
    }
  }

  handleSelectChange(name: string, value: any) {
    if (this.state.readOnly) {
      return;
    }
    this.item[name] = value;
    this.setState({ item: this.item });
    if (this.props.onChanged) {
      this.props.onChanged(this.props.index, name, value);
    }
  }

  handleRemoveItem() {
    if (this.props.onRemove) {
      this.props.onRemove(this.props.index);
    }
  }

  handlePreview(previewData: PreviewData) {
    this.props.onPreview(previewData);
  }

  render() {
    const values = this.state.item.values || [];

    return (
      <div className="InOutItem">
        <div className="InOutRow">
          <div className="InOutCellTitle">Name:</div>
          <div className="InOutCellValue" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <input
              type="text"
              className="InOutValue"
              name="name"
              value={this.state.item.name}
              onChange={this.handleChange}
              readOnly={this.state.readOnly}
              style={{ flex: 1, minWidth: 0 }}
            />
            {!this.state.readOnly && (
              <IconButton
                size="small"
                className="Remove"
                onClick={() => this.handleRemoveItem()}
                sx={{
                  color: '#888',
                  padding: '2px',
                  flexShrink: 0,
                  '&:hover': {
                    color: '#f44336',
                    backgroundColor: 'rgba(244, 67, 54, 0.08)',
                  },
                }}
                title="Remove"
              >
                <CloseIcon sx={{ fontSize: 16 }} />
              </IconButton>
            )}
          </div>
        </div>

        <div className="InOutRow">
          <div className="InOutCellTitle">Type:</div>
          <PluginsConsumer>
            {(plugins_dict: PluginsDict) => {
              const op = plugins_dict.operations_dict?.[this.props.nodeKind];
              const resources: any[] = op?.resources || [];
              const resourceDesc = plugins_dict.resources_dict[this.state.item.file_type];

              return (
                <div className="InOutCellValue" style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
                  <FormControl size="small" sx={{ flex: 1, minWidth: 0 }}>
                    <Select
                      className="InOutValue"
                      value={this.state.item.file_type || ''}
                      onChange={(e: SelectChangeEvent) => this.handleSelectChange('file_type', e.target.value)}
                      disabled={this.state.readOnly}
                      sx={{
                        height: 24,
                        fontSize: '11pt',
                        color: '#fff',
                        backgroundColor: '#262626',
                        '& .MuiSelect-select': {
                          paddingY: '1px',
                          paddingLeft: '6px',
                        },
                        '& .MuiOutlinedInput-notchedOutline': {
                          borderColor: '#444',
                        },
                      }}
                    >
                      {resources.map((description: any) => (
                        <MenuItem value={description.kind} key={description.kind} sx={{ fontSize: '0.85rem' }}>
                          {description.title}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  {resourceDesc && <Icon type_descriptor={resourceDesc} />}
                </div>
              );
            }}
          </PluginsConsumer>
        </div>

        <div className="InOutRow">
          <div className="InOutCellTitle">Array:</div>
          <div className="InOutCellValue">
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  name="is_array"
                  checked={Boolean(this.state.item.is_array)}
                  disabled={this.state.readOnly}
                  onChange={this.handleChange}
                  color="primary"
                />
              }
              label={
                <Typography variant="body2" sx={{ color: '#fff', fontSize: '11pt', marginLeft: '6px' }}>
                  {this.state.item.is_array ? 'True' : 'False'}
                </Typography>
              }
              sx={{ margin: 0 }}
            />
          </div>
        </div>

        {this.state.item.is_array && (
          <div className="InOutRow">
            <div className="InOutCellTitle">Min size</div>
            <div className="InOutCellValue">
              <div className="InOutValue">
                <input
                  className="CellValue"
                  type="number"
                  name="min_count"
                  min="0"
                  onChange={this.handleChange}
                  value={this.state.item.min_count ?? 0}
                  readOnly={this.state.readOnly}
                />
              </div>
            </div>
          </div>
        )}

        {values.map((resource_id: any) => (
          <OutputItem
            item={this.state.item as any}
            key={resource_id}
            onPreview={(previewData) => this.handlePreview(previewData)}
          />
        ))}
      </div>
    );
  }
}
