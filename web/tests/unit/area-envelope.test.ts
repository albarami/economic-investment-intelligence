import { describe, expect, it } from 'vitest';
import { readEnvelope } from '../../src/api/areas';

const envelope = {
  tool: 'make_area',
  call_id: 'INVENTED-call',
  release_id: 'INVENTED-release',
  engine: 'embedded',
  status: 'NO_DATA',
  blocks: [],
  facts: [],
  payload: null,
  caveat_keys: ['point_without_base_cell'],
};
describe('exact area wire boundary', () => {
  it('preserves a governed caveat with no reason', () => {
    expect(readEnvelope(envelope)).toEqual({ kind: 'envelope', envelope });
  });
  it.each([
    { ...envelope, reason: null },
    { ...envelope, privacy_receipt: null },
    { ...envelope, status: 'INVALID_ARGUMENT' },
    { ...envelope, blocks: undefined },
  ])('refuses a malformed envelope', (value) => {
    expect(readEnvelope(value)).toMatchObject({
      kind: 'refused',
      code: 'malformed',
    });
  });
  it.each([422, 503])('preserves a BE-91 error', (status) => {
    expect(
      readEnvelope(
        {
          error: {
            code: 'INVALID_ARGUMENT',
            message_key: 'invalid_argument',
            error_id: 'INVENTED-error',
          },
        },
        status,
      ),
    ).toEqual({
      kind: 'refused',
      httpStatus: status,
      code: 'INVALID_ARGUMENT',
    });
  });
});
