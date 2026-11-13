import React, { ReactNode } from 'react';

export interface PropertiesBoxProps {
  title: ReactNode;
  children: ReactNode;
  className?: string;
}

export const PropertiesBox: React.FC<PropertiesBoxProps> = ({ title, children, className = '' }) => (
  <div className={`PropertiesBox ${className}`.trim()}>
    <div className="PropertiesBoxHeader">{title}</div>
    <div className="PropertiesBoxContent">{children}</div>
  </div>
);

export default function makePropertiesBox(title: ReactNode, content: ReactNode) {
  return <PropertiesBox title={title}>{content}</PropertiesBox>;
}
