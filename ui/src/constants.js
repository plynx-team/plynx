export const PARAMETER_TYPES = [
  {
    type: 'str',
    alias: 'String',
  },
  {
    type: 'int',
    alias: 'Integer',
  },
  {
    type: 'bool',
    alias: 'Boolean',
  },
  {
    type: 'text',
    alias: 'Text',
  },
  {
    type: 'enum',
    alias: 'Enum',
  },
  {
    type: 'list_str',
    alias: 'List of Strings',
  },
  {
    type: 'list_int',
    alias: 'List of Integers',
  },
  {
    type: 'code',
    alias: 'Code',
  },
];

export const SPECIAL_TYPE_NAMES = ['code'];

export const ACTION = Object.freeze({
  SAVE: 'SAVE',
  APPROVE: 'APPROVE',
  CREATE_RUN: 'CREATE_RUN',
  VALIDATE: 'VALIDATE',
  DEPRECATE: 'DEPRECATE',
  MANDATORY_DEPRECATE: 'MANDATORY_DEPRECATE',
  REARRANGE: 'REARRANGE',
  UPGRADE_NODES: 'UPGRADE_NODES',
  PREVIEW_CMD: 'PREVIEW_CMD',
  CANCEL: 'CANCEL',
  GENERATE_CODE: 'GENERATE_CODE',
});

export const RELOAD_OPTIONS = Object.freeze({
  NONE: 'NONE',
  RELOAD: 'RELOAD',
  NEW_TAB: 'NEW_TAB',
});

export const RESPONCE_STATUS = Object.freeze({
  SUCCESS: 'SUCCESS',
  VALIDATION_FAILED: 'VALIDATION_FAILED',
  FAILED: 'FAILED'
});

export const NODE_STATUS = Object.freeze({
  CREATED: 'CREATED',
  READY: 'READY',
  DEPRECATED: 'DEPRECATED',
  MANDATORY_DEPRECATED: 'MANDATORY_DEPRECATED'
});

export const NODE_RUNNING_STATUS = Object.freeze({
  STATIC: 'STATIC',
  CREATED: 'CREATED',
  IN_QUEUE: 'IN_QUEUE',
  RUNNING: 'RUNNING',
  SUCCESS: 'SUCCESS',
  RESTORED: 'RESTORED',
  FAILED: 'FAILED',
  CANCELED: 'CANCELED',
});

export const GRAPH_RUNNING_STATUS = Object.freeze({
  CREATED: 'CREATED',
  READY: 'READY',
  RUNNING: 'RUNNING',
  SUCCESS: 'SUCCESS',
  FAILED: 'FAILED',
  CANCELED: 'CANCELED',
  FAILED_WAITING: 'FAILED_WAITING',
});

export const FILE_STATUS = Object.freeze({
  READY: 'READY',
  DEPRECATED: 'DEPRECATED',
  MANDATORY_DEPRECATED: 'MANDATORY_DEPRECATED'
});

export const VALIDATION_TARGET_TYPE = Object.freeze({
  NODE: 'NODE',
  GRAPH: 'GRAPH',
  INPUT: 'INPUT',
  PARAMETER: 'PARAMETER',
  PROPERTY: 'PROPERTY',
});

export const VALIDATION_CODES = Object.freeze({
  IN_DEPENDENTS: 'IN_DEPENDENTS',
  MISSING_INPUT: 'MISSING_INPUT',
  MISSING_PARAMETER: 'MISSING_PARAMETER',
  MINIMUM_COUNT_MUST_NOT_BE_NEGATIVE: 'MINIMUM_COUNT_MUST_NOT_BE_NEGATIVE',
  MINIMUM_COUNT_MUST_BE_GREATER_THAN_MAXIMUM: 'MINIMUM_COUNT_MUST_BE_GREATER_THAN_MAXIMUM',
  MAXIMUM_COUNT_MUST_NOT_BE_ZERO: 'MAXIMUM_COUNT_MUST_NOT_BE_ZERO',
  DEPRECATED_NODE: 'DEPRECATED_NODE'
});

export const ALERT_OPTIONS = {
  offset: 14,
  position: 'bottom right',
  theme: 'dark',
  time: 5000,
  transition: 'fade'
};

export const OPERATIONS = ['get_resource', 'bash_jinja2', 'python'];
export const PROGRAMMABLE_OPERATIONS = ['bash_jinja2', 'python'];

export const KEY_MAP = {
  copyPressed: ['command+c', 'ctrl+c'],
  pastePressed: ['command+v', 'ctrl+v'],
  savePressed: ['command+s', 'ctrl+s'],
  deletePressed: ['del', 'backspace'],
  escPressed: ['esc'],
  commandDown: {
    sequence: ['command', 'ctrl'],
    action: 'keydown'
  },
  commandUp: {
    sequence: ['command', 'ctrl'],
    action: 'keyup'
  },
};

export const SPECIAL_USERS = Object.freeze({
  DEMO: 'demo',
  DEFAULT: 'default',
});

export const CODE_LANGUAGES = [
  'python',
  'sh',
];

export const CODE_THEMES = [
  'chaos',
];
