export function storeToClipboard(text: any): void {
  localStorage.setItem('clipboard', JSON.stringify(text));
}

export function loadFromClipboard(): any {
  const item = localStorage.getItem('clipboard');
  return item ? JSON.parse(item) : null;
}

export function utcTimeToLocal(text?: string | null): string {
  if (!text) {
    return '';
  }
  const trimmed = String(text).trim();
  let normalized = trimmed;
  if (!/(?:Z|GMT|[+-]\d{2}:?\d{2})$/i.test(trimmed)) {
    if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}/.test(trimmed)) {
      normalized = `${trimmed.replace(' ', 'T')}Z`;
    } else {
      normalized = `${trimmed} GMT`;
    }
  }
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return trimmed;
  }
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  );
}

export function generateObjectId(): string {
  const timestampHex = Math.floor(Date.now() / 1000).toString(16).padStart(8, '0');
  const bytes = new Uint8Array(8);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 8; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  const randomHex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${timestampHex}${randomHex}`;
}

export function downloadBlob(data: BlobPart, filename: string, mimeType = 'application/octet-stream'): void {
  const blob = data instanceof Blob ? data : new Blob([data], { type: mimeType });
  const blobUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.style.display = 'none';
  link.href = blobUrl;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => window.URL.revokeObjectURL(blobUrl), 100);
}

export interface TourStep {
  selector?: string;
  content: string;
  style?: Record<string, any>;
  [key: string]: any;
}

export function addStyleToTourSteps(steps: TourStep[]): TourStep[] {
  return steps.map((step) => ({
    style: {
      backgroundColor: '#202020',
      color: 'white',
      border: '1px solid #12ccc8',
    },
    ...step,
  }));
}
