import React, { useEffect, useRef, ReactNode } from 'react';

function isEditableElement(target: any): boolean {
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

export interface HotKeysProps {
  className?: string;
  handlers?: Record<string, (e: KeyboardEvent) => void>;
  children?: ReactNode;
  keyMap?: any;
}

export default function HotKeys({ className, handlers = {}, children }: HotKeysProps) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
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
