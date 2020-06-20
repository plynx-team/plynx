import React from 'react';
import PropTypes from 'prop-types';
import { icons } from 'feather-icons';

const DEFAULT_PROPS = {
  xmlns: 'http://www.w3.org/2000/svg',
  width: 10,
  height: 10,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

const RenderIcon = ({ family, name, ...props }) => {
  if (family === 'plynx') {
    return <img
      className='file-type-icon'
      src={"/icons/file_types/" + name + ".svg"}
      {...DEFAULT_PROPS}
      {...props}
      alt={name}
      />;
  }
  if (family === 'feathericons') {
    return <svg
      className='file-type-icon'
      {...DEFAULT_PROPS}
      {...props}
      dangerouslySetInnerHTML={{ __html: icons[name] }}           // eslint-disable-line react/no-danger
    />;
  }
  throw new Error("Unknown icon family " + family);
};

export default function icon(props) {
  const {type_descriptor} = props;
  const icon_descriptor = type_descriptor.icon.split('.');
  let icon_family;
  let icon_name;
  if (icon_descriptor && icon_descriptor.length === 2) {
    icon_family = icon_descriptor[0];
    icon_name = icon_descriptor[1];
  } else {
    console.warn(type_descriptor, 'is not a valid descriptor');
    icon_family = 'feathericons';
    icon_family = 'file';
  }

  return <RenderIcon
    family={icon_family}
    name={icon_name}
    stroke={type_descriptor.color}
    {...props}
  />;
}

icon.propTypes = {
  type_descriptor: PropTypes.shape({
    icon: PropTypes.string.isRequired,
    color: PropTypes.string.isRequired,
  }).isRequired
};
