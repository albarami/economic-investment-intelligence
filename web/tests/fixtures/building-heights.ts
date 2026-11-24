/**
 * The exact body `GET /api/building-heights` serves for the invented asset of
 * `product/tests/test_building_heights_read.py` (SYN-B-*, `.invalid` hosts).
 * That test compares the route's output with this JSON file.
 */
import body from './building-heights.json';

export type HeightsBody = typeof body;

/** A fresh deep copy, so one test's change never reaches another. */
export function heightsBody(): HeightsBody {
  return structuredClone(body);
}
