import React from 'react';
import PropTypes from 'prop-types';
import { icons } from 'feather-icons';

const DEFAULT_PROPS = {
  xmlns: 'http://www.w3.org/2000/svg',
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

export function FeatherIcon({ name, size = 24, ...props }) {
  const iconData = icons[name];
  return (
    <svg
      {...DEFAULT_PROPS}
      width={size}
      height={size}
      {...props}
      dangerouslySetInnerHTML={{ __html: iconData ? iconData.contents : '' }}
    />
  );
}

FeatherIcon.propTypes = {
  name: PropTypes.string.isRequired,
  size: PropTypes.number,
};

const RenderIcon = ({ family, name, ...props }) => {
  if (family === 'plynx') {
    return (
      <img
        className="file-type-icon"
        src={`/icons/file_types/${name}.svg`}
        width={DEFAULT_PROPS.width}
        height={DEFAULT_PROPS.height}
        {...props}
        alt={name}
      />
    );
  }
  if (family === 'feathericons') {
    const iconData = icons[name];
    return (
      <svg
        className="file-type-icon"
        {...DEFAULT_PROPS}
        {...props}
        dangerouslySetInnerHTML={{ __html: iconData ? iconData.contents : '' }}
      />
    );
  }
  throw new Error(`Unknown icon family ${family}`);
};

RenderIcon.propTypes = {
  family: PropTypes.string.isRequired,
  name: PropTypes.string.isRequired,
};

export default function Icon(props) {
  const { type_descriptor, ...restProps } = props;
  const icon_descriptor = type_descriptor.icon.split('.');
  let icon_family;
  let icon_name;
  if (icon_descriptor && icon_descriptor.length === 2) {
    icon_family = icon_descriptor[0];
    icon_name = icon_descriptor[1];
  } else {
    console.warn(type_descriptor, 'is not a valid descriptor');
    icon_family = 'feathericons';
    icon_name = 'file';
  }

  return (
    <RenderIcon
      family={icon_family}
      name={icon_name}
      stroke={type_descriptor.color}
      {...restProps}
    />
  );
}

Icon.propTypes = {
  type_descriptor: PropTypes.shape({
    icon: PropTypes.string.isRequired,
    color: PropTypes.string.isRequired,
  }).isRequired,
};
