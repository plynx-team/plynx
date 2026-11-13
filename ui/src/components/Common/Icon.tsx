import React, { SVGProps } from 'react';
// @ts-ignore
import { icons } from 'feather-icons';

const DEFAULT_PROPS = {
  xmlns: 'http://www.w3.org/2000/svg',
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export interface FeatherIconProps extends SVGProps<SVGSVGElement> {
  name: string;
  size?: number;
}

export function FeatherIcon({ name, size = 24, ...props }: FeatherIconProps) {
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

interface RenderIconProps {
  family: string;
  name: string;
  stroke?: string;
  className?: string;
  [key: string]: any;
}

const RenderIcon: React.FC<RenderIconProps> = ({ family, name, ...props }) => {
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

export interface IconTypeDescriptor {
  icon: string;
  color: string;
  [key: string]: any;
}

export interface IconProps {
  type_descriptor: IconTypeDescriptor;
  className?: string;
  [key: string]: any;
}

export default function Icon({ type_descriptor, ...restProps }: IconProps) {
  const iconDescriptor = type_descriptor && type_descriptor.icon ? type_descriptor.icon.split('.') : null;
  let iconFamily: string;
  let iconName: string;
  if (iconDescriptor && iconDescriptor.length === 2) {
    iconFamily = iconDescriptor[0];
    iconName = iconDescriptor[1];
  } else {
    console.warn(type_descriptor, 'is not a valid descriptor');
    iconFamily = 'feathericons';
    iconName = 'file';
  }

  return (
    <RenderIcon
      family={iconFamily}
      name={iconName}
      stroke={type_descriptor ? type_descriptor.color : 'currentColor'}
      {...restProps}
    />
  );
}
