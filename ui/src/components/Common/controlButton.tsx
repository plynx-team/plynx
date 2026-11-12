import React, { ChangeEvent, MouseEvent } from 'react';
import SearchBar from './SearchBar';
import { styled } from '@mui/material/styles';
import Switch from '@mui/material/Switch';
import Divider from '@mui/material/Divider';

export interface ControlButtonProps {
  func?: (e?: MouseEvent<any>) => void;
  href?: string;
  className?: string;
  img: string;
  text: string;
  selected?: boolean;
  enabled?: boolean;
  key?: string | number;
  [key: string]: any;
}

export const ControlButton: React.FC<ControlButtonProps> = ({
  func,
  href,
  className = '',
  img,
  text,
  selected = false,
  enabled = true,
}) => {
  const classNames = [
    'control-button',
    className,
    selected ? 'selected' : '',
    enabled ? 'enabled' : 'disabled',
  ]
    .filter(Boolean)
    .join(' ');

  const content = (
    <>
      <img src={`/icons/${img}`} alt={text} />
      <div className="control-button-text">{text}</div>
    </>
  );

  if (href) {
    return (
      <a href={href} className={classNames}>
        {content}
      </a>
    );
  }

  return (
    <div
      onClick={(e) => {
        e.preventDefault();
        if (enabled && func) {
          func(e);
        }
      }}
      className={classNames}
    >
      {content}
    </div>
  );
};

export function makeControlButton(props: ControlButtonProps) {
  return <ControlButton {...props} key={props.key ?? props.text} />;
}

export function makeControlLink(props: ControlButtonProps) {
  return <ControlButton {...props} key={props.key ?? props.text} />;
}

export interface ControlSeparatorProps {
  key?: string | number;
}

export function makeControlSeparator(props: ControlSeparatorProps) {
  return (
    <Divider
      orientation="vertical"
      flexItem
      className="control-separator"
      key={props.key}
      sx={{
        backgroundColor: '#444',
        margin: '6px 8px',
        alignSelf: 'stretch',
        height: 'auto',
      }}
    />
  );
}

export interface ToggleItem extends ControlButtonProps {
  value?: any;
}

export interface ControlTogglesProps {
  key?: string | number;
  items: ToggleItem[];
  func?: (value: any) => void;
  onIndexChange: (index: number) => void;
  index: number;
}

export function makeControlToggles(props: ControlTogglesProps) {
  return (
    <div className="control-toggle" key={props.key}>
      {props.items.map((item, index) => {
        const buttonItem: ControlButtonProps = { ...item };
        if (index === props.index) {
          buttonItem.selected = true;
        }
        buttonItem.key = index;
        buttonItem.func = () => {
          if (props.func) {
            props.func(item.value);
          }
          props.onIndexChange(index);
        };
        if (index === 0) {
          buttonItem.className = 'first';
        }
        if (index === props.items.length - 1) {
          buttonItem.className = 'last';
        }

        return makeControlButton(buttonItem);
      })}
    </div>
  );
}

export interface ControlSearchBarProps {
  func: (search: string) => void;
  search: string;
}

export function makeControlSearchBar(props: ControlSearchBarProps) {
  return (
    <SearchBar
      onSearchUpdate={(search) => props.func(search)}
      search={props.search}
    />
  );
}

const tmpLabel = { inputProps: { 'aria-label': 'Switch demo' } };

const StyledSwitch = styled(Switch)(() => ({
  '& .MuiSwitch-track': {
    backgroundColor: '#eee',
  },
}));

export interface ControlCheckboxProps {
  func: (e: ChangeEvent<HTMLInputElement>, checked: boolean) => void;
  className?: string;
  text: string;
  checked?: boolean;
  enabled?: boolean;
  visible?: boolean;
}

export function makeControlCheckbox(props: ControlCheckboxProps) {
  const isEnabled = props.enabled !== false;
  const isVisible = props.visible !== false;

  return (
    <div
      key={props.text}
      className={[
        'control-checkbox',
        props.className || '',
        isEnabled ? 'enabled' : 'disabled',
        isVisible ? 'visible' : 'hidden',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <div className="control-checkbox-text">{props.text}:</div>
      <StyledSwitch
        {...tmpLabel}
        checked={Boolean(props.checked)}
        disabled={!isEnabled}
        onChange={props.func}
        size="small"
      />
    </div>
  );
}

export interface PanelItem {
  render: (props: any) => React.ReactNode;
  props: any;
}

export interface ControlPanelProps {
  props?: {
    key?: string | number;
    items?: PanelItem[];
    [key: string]: any;
  };
  key?: string | number;
  items?: PanelItem[];
  children_func?: () => React.ReactNode;
}

export function makeControlPanel(args: ControlPanelProps = {}) {
  const panelKey = args.key || (args.props && args.props.key) || 'panel';
  const panelItems = args.items || (args.props && args.props.items) || [];

  return (
    <div className="control-panel" key={panelKey}>
      {args.children_func && args.children_func()}
      {panelItems.map((item: PanelItem) => item.render(item.props))}
    </div>
  );
}

export default ControlButton;
