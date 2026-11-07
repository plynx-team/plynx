import React, { useEffect, useRef } from 'react';
import PropTypes from 'prop-types';

function isEditableElement(target) {
  if (!target || !target.tagName) {
    return false;
  }
  const tag = target.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable) {
    return true;
  }
  if (typeof target.closest === 'function' && target.closest('.ace_editor')) {
    return true;
  }
  return false;
}

export default function HotKeys({ className, handlers = {}, children }) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    const onKeyDown = (event) => {
      const currentHandlers = handlersRef.current || {};
      if (event.key === 'Escape' && currentHandlers.escPressed) {
        currentHandlers.escPressed(event);
        return;
      }

      if (isEditableElement(event.target)) {
        return;
      }

      const mod = event.metaKey || event.ctrlKey;
      const key = (event.key || '').toLowerCase();
      if (mod && key === 'c' && currentHandlers.copyPressed) {
        currentHandlers.copyPressed(event);
      } else if (mod && key === 'v' && currentHandlers.pastePressed) {
        currentHandlers.pastePressed(event);
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return <div className={className}>{children}</div>;
}

HotKeys.propTypes = {
  className: PropTypes.string,
  handlers: PropTypes.object,
  children: PropTypes.node,
};
