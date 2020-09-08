import { ObjectID } from 'bson';


export const PARAMETER_TYPES = [
  {
    type: 'str', // same as in parameter_types.py
    alias: 'String', // for humans reading in UI
  },
  {
    type: 'int',
    alias: 'Integer',
  },
  {
    type: 'float',
    alias: 'Float',
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
  REARRANGE_NODES: 'REARRANGE_NODES',
  UPGRADE_NODES: 'UPGRADE_NODES',
  PREVIEW_CMD: 'PREVIEW_CMD',
  CANCEL: 'CANCEL',
  GENERATE_CODE: 'GENERATE_CODE',
  CLONE: 'CLONE',
});

export const RELOAD_OPTIONS = Object.freeze({
  NONE: 'NONE',
  RELOAD: 'RELOAD',
  NEW_TAB: 'NEW_TAB',
  OPEN_NEW_LINK: 'OPEN_NEW_LINK',
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
  READY: 'READY',
  IN_QUEUE: 'IN_QUEUE',
  RUNNING: 'RUNNING',
  SUCCESS: 'SUCCESS',
  RESTORED: 'RESTORED',
  FAILED: 'FAILED',
  CANCELED: 'CANCELED',
  FAILED_WAITING: 'FAILED_WAITING',
  SPECIAL: 'SPECIAL',
});

export const ACTIVE_NODE_RUNNING_STATUSES = Object.freeze(new Set([
  NODE_RUNNING_STATUS.READY,
  NODE_RUNNING_STATUS.IN_QUEUE,
  NODE_RUNNING_STATUS.RUNNING,
  NODE_RUNNING_STATUS.FAILED_WAITING,
]));

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
  MAXIMUM_COUNT_MUST_BE_GREATER_THAN_MINIMUM: 'MAXIMUM_COUNT_MUST_BE_GREATER_THAN_MINIMUM',
  MAXIMUM_COUNT_MUST_NOT_BE_ZERO: 'MAXIMUM_COUNT_MUST_NOT_BE_ZERO',
  DEPRECATED_NODE: 'DEPRECATED_NODE',
  EMPTY_GRAPH: 'EMPTY_GRAPH',
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

export const COLLECTIONS = Object.freeze({
  TEMPLATES: 'templates',
  RUNS: 'runs',
  GROUPS: 'groups',
  USERS: 'users',
});

export const VIRTUAL_COLLECTIONS = Object.freeze({
  OPERATIONS: 'operations',
  WORKFLOWS: 'workflows',
  RUNS: 'runs',
  GROUPS: 'groups',
});

export const SPECIAL_NODE_IDS = Object.freeze({
  INPUT: new ObjectID('2419f9500000000000000000').toString(),
  OUTPUT: new ObjectID('56274ccc0000000000000000').toString(),
});

export const IAM_POLICIES = Object.freeze({
  CAN_VIEW_OTHERS_OPERATIONS: 'CAN_VIEW_OTHERS_OPERATIONS',
  CAN_VIEW_OTHERS_WORKFLOWS: 'CAN_VIEW_OTHERS_WORKFLOWS',
  CAN_VIEW_OPERATIONS: 'CAN_VIEW_OPERATIONS',
  CAN_VIEW_WORKFLOWS: 'CAN_VIEW_WORKFLOWS',

  CAN_CREATE_OPERATIONS: 'CAN_CREATE_OPERATIONS',
  CAN_CREATE_WORKFLOWS: 'CAN_CREATE_WORKFLOWS',

  CAN_MODIFY_OTHERS_WORKFLOWS: 'CAN_MODIFY_OTHERS_WORKFLOWS',

  CAN_RUN_WORKFLOWS: 'CAN_RUN_WORKFLOWS',

  IS_ADMIN: 'IS_ADMIN',
});

export const OPERATION_VIEW_SETTING = Object.freeze({
  KIND_AND_TITLE: 'KIND_AND_TITLE',
  TITLE_AND_DESCRIPTION: 'TITLE_AND_DESCRIPTION',
});

export const USER_POST_ACTION = Object.freeze({
  CREATE: 'CREATE',
  MODIFY: 'MODIFY',
});

export const REGISTER_USER_EXCEPTION_CODE = Object.freeze({
  EMPTY_USERNAME: {
    username: 'Username required',
  },
  EMPTY_PASSWORD: {
    password: 'Password required',
  },
  USERNAME_ALREADY_EXISTS: {
    username: 'Username already taken',
  },
  EMAIL_ALREADY_EXISTS: {
    email: 'Email already taken',
  },
  INVALID_EMAIL: {
    email: 'Invalid email',
  },
  INVALID_LENGTH_OF_USERNAME: {
    username: 'Plese use 6 to 22 characters',
  },
});

export const DEFAULT_WORKFLOW_KIND = 'basic-dag-workflow';
