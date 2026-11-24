// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { rememberRequest } from '../visual/request-log';

describe('drawing harness request log', () => {
  it('keeps every body and leaves the latest on the singular attribute', () => {
    const root = document.createElement('html');
    rememberRequest(root, 'areaRequest', '{"cutoff":5}');
    rememberRequest(root, 'areaRequest', '{"cutoff":10}');
    expect(JSON.parse(root.dataset.areaRequests ?? '[]')).toEqual([
      '{"cutoff":5}',
      '{"cutoff":10}',
    ]);
    expect(root.dataset.areaRequest).toBe('{"cutoff":10}');
    rememberRequest(root, 'shapeRequest', '{"geometry":1}');
    expect(root.dataset.areaRequests).toBe(
      JSON.stringify(['{"cutoff":5}', '{"cutoff":10}']),
    );
    expect(JSON.parse(root.dataset.shapeRequests ?? '[]')).toEqual([
      '{"geometry":1}',
    ]);
  });
});
