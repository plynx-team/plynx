export interface CookieOptions {
  path?: string;
  maxAge?: number;
  expires?: Date;
  domain?: string;
  secure?: boolean;
  sameSite?: 'Lax' | 'Strict' | 'None';
}

function parseCookies(): Record<string, string> {
  if (typeof document === 'undefined' || !document.cookie) {
    return {};
  }
  const result: Record<string, string> = {};
  const pairs = document.cookie.split(';');
  for (const pair of pairs) {
    const idx = pair.indexOf('=');
    if (idx === -1) {
      continue;
    }
    const rawKey = pair.slice(0, idx).trim();
    const rawVal = pair.slice(idx + 1).trim();
    try {
      result[decodeURIComponent(rawKey)] = decodeURIComponent(rawVal);
    } catch {
      result[rawKey] = rawVal;
    }
  }
  return result;
}

function load(name: string, doNotParse = false): any {
  const cookies = parseCookies();
  const value = cookies[name];
  if (typeof value === 'undefined') {
    return undefined;
  }
  if (doNotParse) {
    return value;
  }
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function save(name: string, val: any, opt: CookieOptions = {}): void {
  if (typeof document === 'undefined') {
    return;
  }
  const serialized = typeof val === 'object' ? JSON.stringify(val) : String(val);
  const parts = [`${encodeURIComponent(name)}=${encodeURIComponent(serialized)}`];
  const path = opt.path || '/';
  parts.push(`path=${path}`);
  if (typeof opt.maxAge === 'number') {
    parts.push(`max-age=${opt.maxAge}`);
  }
  if (opt.expires instanceof Date) {
    parts.push(`expires=${opt.expires.toUTCString()}`);
  }
  if (opt.domain) {
    parts.push(`domain=${opt.domain}`);
  }
  if (opt.secure) {
    parts.push('secure');
  }
  parts.push(`samesite=${opt.sameSite || 'Lax'}`);
  document.cookie = parts.join('; ');
}

function remove(name: string, opt: CookieOptions = {}): void {
  if (typeof document === 'undefined') {
    return;
  }
  const path = opt.path || '/';
  const parts = [
    `${encodeURIComponent(name)}=`,
    `path=${path}`,
    'expires=Thu, 01 Jan 1970 00:00:00 GMT',
    'max-age=0',
  ];
  if (opt.domain) {
    parts.push(`domain=${opt.domain}`);
  }
  document.cookie = parts.join('; ');
}

const cookie = {
  load,
  save,
  remove,
};

export default cookie;
