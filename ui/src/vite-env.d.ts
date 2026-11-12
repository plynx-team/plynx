/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly REACT_APP_BACKEND_HOST?: string;
  readonly VITE_BACKEND_HOST?: string;
  [key: string]: any;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
