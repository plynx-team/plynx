import { describe, it, expect } from 'vitest';
import { reorder } from './ReorderableList';

describe('reorder', () => {
  it('moves an item forward in the list', () => {
    const list = ['a', 'b', 'c', 'd'];
    const result = reorder(list, 0, 2);
    expect(result).toEqual(['b', 'c', 'a', 'd']);
  });

  it('moves an item backward in the list', () => {
    const list = ['a', 'b', 'c', 'd'];
    const result = reorder(list, 3, 1);
    expect(result).toEqual(['a', 'd', 'b', 'c']);
  });

  it('keeps list identical if start and end indices are equal', () => {
    const list = [1, 2, 3];
    const result = reorder(list, 1, 1);
    expect(result).toEqual([1, 2, 3]);
  });

  it('does not mutate the original list', () => {
    const list = ['x', 'y', 'z'];
    const copy = [...list];
    reorder(list, 0, 2);
    expect(list).toEqual(copy);
  });
});
