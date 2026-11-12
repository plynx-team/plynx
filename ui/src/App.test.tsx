import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import App from './App';
import cookie from './cookie';
import { generateObjectId, utcTimeToLocal } from './utils';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
};

describe('PLynx UI', () => {
  it('renders login route without crashing', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={['/login']} future={ROUTER_FUTURE}>
          <App />
        </MemoryRouter>
      );
    });

    expect(container.querySelector('.App')).not.toBeNull();
    expect(container.textContent).toContain('Please sign in to continue');

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  it('renders 404 route without crashing', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={['/unknown-route']} future={ROUTER_FUTURE}>
          <App />
        </MemoryRouter>
      );
    });

    expect(container.textContent).toContain('404: not found');

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  it('saves, loads, and removes JSON and string cookies', () => {
    cookie.save('test_user', { username: 'alice', policies: ['IS_ADMIN'] }, { path: '/' });
    expect(cookie.load('test_user')).toEqual({ username: 'alice', policies: ['IS_ADMIN'] });

    cookie.save('access_token', 'abc123', { path: '/' });
    expect(cookie.load('access_token')).toBe('abc123');

    cookie.remove('test_user', { path: '/' });
    cookie.remove('access_token', { path: '/' });
    expect(cookie.load('test_user')).toBeUndefined();
    expect(cookie.load('access_token')).toBeUndefined();
  });

  it('generates valid 24-hex ObjectIds and formats UTC timestamps', () => {
    const id1 = generateObjectId();
    const id2 = generateObjectId();
    expect(id1).toMatch(/^[0-9a-f]{24}$/);
    expect(id2).toMatch(/^[0-9a-f]{24}$/);
    expect(id1).not.toBe(id2);

    expect(utcTimeToLocal('2026-01-15T12:30:45')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    expect(utcTimeToLocal('2026-01-15T12:30:45.123456+00:00')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    expect(utcTimeToLocal('2026-01-15 12:30:45')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
  });
});
