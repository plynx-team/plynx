import { describe, it, expect } from 'vitest';
import { validatePassword } from './passwordUtils';

describe('validatePassword', () => {
  it('accepts passwords with >= 8 chars containing uppercase, lowercase, and digits', () => {
    expect(validatePassword('Secret123')).toBe(true);
    expect(validatePassword('PlynxPassword2026')).toBe(true);
  });

  it('rejects passwords shorter than 8 characters', () => {
    expect(validatePassword('')).toBe(false);
    expect(validatePassword('12345')).toBe(false);
    expect(validatePassword('Sec123')).toBe(false);
  });

  it('rejects passwords missing required character groups', () => {
    expect(validatePassword('lowercase123')).toBe(false); // missing uppercase
    expect(validatePassword('UPPERCASE123')).toBe(false); // missing lowercase
    expect(validatePassword('NoDigitsHere')).toBe(false);  // missing digits
  });
});
