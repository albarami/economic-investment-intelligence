import { describe, expect, it } from 'vitest';

import { subjectAllows } from '../../src/brief/catalogue';

describe('register company slots', () => {
  it('admits a public card fact', () => {
    expect(subjectAllows('register_company', 'public', 'card')).toBe(true);
  });

  it('refuses a synthetic wage fact', () => {
    expect(subjectAllows('register_company', 'synthetic', 'wage')).toBe(false);
  });

  it('refuses an employee count of the wrong class', () => {
    expect(subjectAllows('register_company', 'public', 'employee_count')).toBe(
      false,
    );
    expect(
      subjectAllows('register_company', 'simulated', 'employee_count'),
    ).toBe(false);
  });

  it('admits only the synthetic employee count', () => {
    expect(
      subjectAllows('register_company', 'synthetic', 'employee_count'),
    ).toBe(true);
    expect(subjectAllows('register_company', 'simulated', 'card')).toBe(false);
    expect(subjectAllows('register_company', 'synthetic', 'card')).toBe(false);
  });
});
