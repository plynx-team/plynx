import React from 'react';

export function listTextElement(className, text, key) {
  return (
      <div className={className}
        key={key}
        >
        <div className='list-field'>
          {text}
        </div>
      </div>
  );
}
