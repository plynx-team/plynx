import React, { ReactNode } from 'react';

export function listTextElement(className: string, text: ReactNode, key?: string | number) {
  return (
    <div className={className} key={key}>
      <div className="list-field">{text}</div>
    </div>
  );
}

export function renderStatus(status: string) {
  return <div className={`status-badge ${status}`}>{status}</div>;
}
