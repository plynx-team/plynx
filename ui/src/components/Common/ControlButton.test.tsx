import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi } from 'vitest';
import ControlButton from './ControlButton';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

describe('ControlButton', () => {
  it('renders button and handles click when enabled', async () => {
    const handleClick = vi.fn();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <ControlButton
          text="Run Workflow"
          img="play.svg"
          func={handleClick}
          enabled={true}
        />
      );
    });

    const button = container.querySelector('.control-button') as HTMLElement;
    expect(button).not.toBeNull();
    expect(button.textContent).toContain('Run Workflow');

    await act(async () => {
      button.click();
    });

    expect(handleClick).toHaveBeenCalledTimes(1);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  it('renders in disabled state and does not trigger click', async () => {
    const handleClick = vi.fn();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <ControlButton
          text="Disabled Action"
          img="save.svg"
          func={handleClick}
          enabled={false}
        />
      );
    });

    const button = container.querySelector('.control-button') as HTMLElement;
    expect(button).not.toBeNull();
    expect(button.className).toContain('disabled');

    await act(async () => {
      button.click();
    });

    expect(handleClick).not.toHaveBeenCalled();

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});
