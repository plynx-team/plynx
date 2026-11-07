import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';

export default function CacheBuster({
  children,
  currentVersion,
  isEnabled = false,
  isVerboseMode = false,
  loadingComponent = null,
  metaFileDirectory = '.',
}) {
  const [loading, setLoading] = useState(isEnabled);
  globalThis.appVersion = currentVersion;

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
    return loadingComponent;
  }

  return <>{children}</>;
}

CacheBuster.propTypes = {
  children: PropTypes.node,
  currentVersion: PropTypes.string.isRequired,
  isEnabled: PropTypes.bool,
  isVerboseMode: PropTypes.bool,
  loadingComponent: PropTypes.node,
  metaFileDirectory: PropTypes.string,
};
