import { describe, it, expect } from 'vitest';
import { isValidConnection } from './OperationNode';
import { Connection } from 'reactflow';

describe('isValidConnection', () => {
  const createMockRegistry = () => ({
    node_a: {
      node: {
        _id: 'node_a',
        outputs: [
          { name: 'out_file', file_type: 'file' },
          { name: 'out_csv', file_type: 'csv' },
        ],
        inputs: [],
      },
    },
    node_b: {
      node: {
        _id: 'node_b',
        inputs: [
          { name: 'in_file', file_type: 'file', is_array: false, input_references: [] },
          { name: 'in_csv', file_type: 'csv', is_array: true, input_references: [] },
          { name: 'in_occupied', file_type: 'file', is_array: false, input_references: [{ node_id: 'node_c', output_id: 'out' }] },
        ],
        outputs: [],
      },
    },
  });

  it('allows connection between matching types', () => {
    const registry = createMockRegistry();
    const conn: Connection = {
      source: 'node_a',
      sourceHandle: 'out_file',
      target: 'node_b',
      targetHandle: 'in_file',
    };
    expect(isValidConnection(conn, registry)).toBe(true);
  });

  it('rejects connection when file types do not match', () => {
    const registry = createMockRegistry();
    const conn: Connection = {
      source: 'node_a',
      sourceHandle: 'out_file',
      target: 'node_b',
      targetHandle: 'in_csv',
    };
    expect(isValidConnection(conn, registry)).toBe(false);
  });

  it('rejects second connection to non-array input that already has references', () => {
    const registry = createMockRegistry();
    const conn: Connection = {
      source: 'node_a',
      sourceHandle: 'out_file',
      target: 'node_b',
      targetHandle: 'in_occupied',
    };
    expect(isValidConnection(conn, registry)).toBe(false);
  });

  it('allows connection to array input even with existing references', () => {
    const registry = createMockRegistry();
    registry.node_b.node.inputs[1].input_references = [{ node_id: 'node_c', output_id: 'out' }];
    const conn: Connection = {
      source: 'node_a',
      sourceHandle: 'out_csv',
      target: 'node_b',
      targetHandle: 'in_csv',
    };
    expect(isValidConnection(conn, registry)).toBe(true);
  });

  it('returns false for missing source or target node or handle', () => {
    const registry = createMockRegistry();
    expect(isValidConnection({ source: null, target: 'node_b', sourceHandle: null, targetHandle: null }, registry)).toBe(false);
    expect(isValidConnection({ source: 'node_a', target: 'unknown', sourceHandle: 'out_file', targetHandle: 'in_file' }, registry)).toBe(false);
    expect(isValidConnection({ source: 'node_a', target: 'node_b', sourceHandle: 'nonexistent', targetHandle: 'in_file' }, registry)).toBe(false);
  });
});
