import React from 'react';

export function listTextElement(className, text) {
  return <div className={className}>
    <div className='list-field'>
      {text}
    </div>
  </div>;
}
