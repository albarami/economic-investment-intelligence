// A small reader of Mapbox Vector Tile buffers (specification version 2.1):
// layer names, extents, feature properties and polygon rings in tile units.
// It reads only what the look page's release build needs and refuses what it
// does not understand. Tested in tests/release.node-test.mjs.

const WIRE_VARINT = 0;
const WIRE_64 = 1;
const WIRE_BYTES = 2;
const WIRE_32 = 5;

function reader(bytes) {
  let at = 0;
  const varint = () => {
    let result = 0;
    let shift = 0;
    for (;;) {
      if (at >= bytes.length) throw new Error('vector tile: truncated varint');
      const byte = bytes[at];
      at += 1;
      result += (byte & 0x7f) * 2 ** shift;
      if (byte < 0x80) return result;
      shift += 7;
      if (shift > 63) throw new Error('vector tile: varint too long');
    }
  };
  const take = (length) => {
    if (at + length > bytes.length)
      throw new Error('vector tile: truncated field');
    const part = bytes.subarray(at, at + length);
    at += length;
    return part;
  };
  return {
    done: () => at >= bytes.length,
    key: () => {
      const key = varint();
      return { field: Math.floor(key / 8), wire: key % 8 };
    },
    varint,
    bytes: () => take(varint()),
    skip: (wire) => {
      if (wire === WIRE_VARINT) varint();
      else if (wire === WIRE_64) take(8);
      else if (wire === WIRE_BYTES) take(varint());
      else if (wire === WIRE_32) take(4);
      else throw new Error(`vector tile: unknown wire type ${wire}`);
    },
    // Copy through Uint8Array.from. Buffer.slice shares its pool, so a
    // DataView on that buffer would not start at these bytes.
    double: () => {
      const part = Uint8Array.from(take(8));
      return new DataView(
        part.buffer,
        part.byteOffset,
        part.byteLength,
      ).getFloat64(0, true);
    },
    float: () => {
      const part = Uint8Array.from(take(4));
      return new DataView(
        part.buffer,
        part.byteOffset,
        part.byteLength,
      ).getFloat32(0, true);
    },
  };
}

const text = new TextDecoder();

function zigzag(value) {
  return value % 2 === 0 ? value / 2 : -(value + 1) / 2;
}

function packed(bytes) {
  const read = reader(bytes);
  const values = [];
  while (!read.done()) values.push(read.varint());
  return values;
}

function value(bytes) {
  const read = reader(bytes);
  let found = null;
  while (!read.done()) {
    const { field, wire } = read.key();
    if (field === 1 && wire === WIRE_BYTES) found = text.decode(read.bytes());
    else if (field === 2 && wire === WIRE_32) found = read.float();
    else if (field === 3 && wire === WIRE_64) found = read.double();
    else if ((field === 4 || field === 5) && wire === WIRE_VARINT)
      found = read.varint();
    else if (field === 6 && wire === WIRE_VARINT) found = zigzag(read.varint());
    else if (field === 7 && wire === WIRE_VARINT) found = read.varint() === 1;
    else read.skip(wire);
  }
  return found;
}

// Geometry commands (section 4.3 of the specification): MoveTo 1, LineTo 2,
// ClosePath 7, with zigzag-encoded parameters relative to the cursor.
export function rings(commands) {
  const out = [];
  let ring = null;
  let x = 0;
  let y = 0;
  let index = 0;
  while (index < commands.length) {
    const command = commands[index] ?? 0;
    index += 1;
    const id = command & 0x7;
    const count = command >> 3;
    if (id === 1 || id === 2) {
      for (let step = 0; step < count; step += 1) {
        if (index + 1 >= commands.length)
          throw new Error('vector tile: truncated geometry');
        x += zigzag(commands[index] ?? 0);
        y += zigzag(commands[index + 1] ?? 0);
        index += 2;
        if (id === 1) {
          ring = [];
          out.push(ring);
        }
        if (ring === null) throw new Error('vector tile: LineTo before MoveTo');
        ring.push([x, y]);
      }
    } else if (id === 7) {
      if (ring !== null && ring.length > 0) ring.push(ring[0]);
    } else {
      throw new Error(`vector tile: unknown command ${id}`);
    }
  }
  return out;
}

function feature(bytes, keys, values) {
  const read = reader(bytes);
  const properties = {};
  let type = 0;
  let geometry = [];
  while (!read.done()) {
    const { field, wire } = read.key();
    if (field === 2 && wire === WIRE_BYTES) {
      const tags = packed(read.bytes());
      for (let at = 0; at + 1 < tags.length; at += 2) {
        const key = keys[tags[at] ?? -1];
        if (key !== undefined) properties[key] = values[tags[at + 1] ?? -1];
      }
    } else if (field === 3 && wire === WIRE_VARINT) type = read.varint();
    else if (field === 4 && wire === WIRE_BYTES)
      geometry = packed(read.bytes());
    else read.skip(wire);
  }
  return { type, properties, geometry };
}

function layer(bytes, wanted) {
  const read = reader(bytes);
  let name = '';
  let extent = 4096;
  const keys = [];
  const values = [];
  const raw = [];
  while (!read.done()) {
    const { field, wire } = read.key();
    if (field === 1 && wire === WIRE_BYTES) name = text.decode(read.bytes());
    else if (field === 2 && wire === WIRE_BYTES) raw.push(read.bytes());
    else if (field === 3 && wire === WIRE_BYTES)
      keys.push(text.decode(read.bytes()));
    else if (field === 4 && wire === WIRE_BYTES)
      values.push(value(read.bytes()));
    else if (field === 5 && wire === WIRE_VARINT) extent = read.varint();
    else read.skip(wire);
  }
  if (!wanted.includes(name)) return { name, extent, features: null };
  return {
    name,
    extent,
    features: raw.map((part) => feature(part, keys, values)),
  };
}

// Decodes the layers named in `wanted`; other layers keep only their name.
export function decodeTile(buffer, wanted) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  const read = reader(bytes);
  const layers = {};
  while (!read.done()) {
    const { field, wire } = read.key();
    if (field === 3 && wire === WIRE_BYTES) {
      const decoded = layer(read.bytes(), wanted);
      layers[decoded.name] = decoded;
    } else read.skip(wire);
  }
  return layers;
}

// Signed area of a ring by the shoelace formula, in squared tile units.
export function ringArea(ring) {
  let sum = 0;
  for (let index = 0; index + 1 < ring.length; index += 1) {
    const [x1, y1] = ring[index];
    const [x2, y2] = ring[index + 1];
    sum += x1 * y2 - x2 * y1;
  }
  return sum / 2;
}
