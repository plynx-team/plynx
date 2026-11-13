import React, { useEffect, useState, ReactNode } from 'react';

export interface CacheBusterProps {
  children?: ReactNode;
  currentVersion: string;
  isEnabled?: boolean;
  isVerboseMode?: boolean;
  loadingComponent?: ReactNode;
  metaFileDirectory?: string;
}

export default function CacheBuster({
  children,
  currentVersion,
  isEnabled = false,
  isVerboseMode = false,
  loadingComponent = null,
  metaFileDirectory = '.',
}: CacheBusterProps) {
  const [loading, setLoading] = useState(isEnabled);
  (globalThis as any).appVersion = currentVersion;

  useEffect(() => {
    if (!isEnabled) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    const prefix = metaFileDirectory && metaFileDirectory !== '.' ? metaFileDirectory.replace(/\/$/, '') : '';
    fetch(`${prefix}/meta.json`, { cache: 'no-store' })
      .then((res) => (res.ok ? res.json() : null))
      .then(async (meta) => {
        if (meta && meta.version && meta.version !== currentVersion) {
          if (isVerboseMode) {
            console.log(`New version ${meta.version} available (current: ${currentVersion}). Refreshing cache.`);
          }
          if ('caches' in window) {
            const names = await window.caches.keys();
            await Promise.all(names.map((name) => window.caches.delete(name)));
          }
          window.location.reload();
          return;
        }
        if (!cancelled) {
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentVersion, isEnabled, isVerboseMode, metaFileDirectory]);

  if (loading) {
    return <>{loadingComponent}</>;
  }

  return <>{children}</>;
}
