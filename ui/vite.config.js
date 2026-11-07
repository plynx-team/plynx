import { defineConfig, transformWithEsbuild } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => ({
  plugins: [
    {
      name: 'treat-js-files-as-jsx',
      enforce: 'pre',
      async transform(code, id) {
        if (!/\/src\/.*\.js$/.test(id)) {
          return null;
        }
        return transformWithEsbuild(code, id, {
          loader: 'jsx',
          jsx: 'automatic',
        });
      },
    },
    react(),
  ],
  envPrefix: ['VITE_', 'REACT_APP_'],
  define: {
    global: 'globalThis',
    'process.env.NODE_ENV': JSON.stringify(
      mode === 'test' ? 'test' : mode === 'production' ? 'production' : 'development'
    ),
    'process.env.REACT_APP_BACKEND_HOST': JSON.stringify(process.env.REACT_APP_BACKEND_HOST || ''),
  },
  optimizeDeps: {
    esbuildOptions: {
      loader: {
        '.js': 'jsx',
      },
    },
  },
  server: {
    port: 3000,
    host: true,
  },
  build: {
    outDir: 'build',
    assetsDir: 'static',
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined;
          }
          if (id.includes('ace-builds') || id.includes('react-ace')) {
            return 'vendor-ace';
          }
          if (id.includes('@mui') || id.includes('@emotion')) {
            return 'vendor-mui';
          }
          if (id.includes('reactflow') || id.includes('@reactflow') || id.includes('@hello-pangea')) {
            return 'vendor-flow';
          }
          if (id.includes('react-dom') || id.includes('react-router') || id.includes('@remix-run')) {
            return 'vendor-react';
          }
          return undefined;
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
}));
