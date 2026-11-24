import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { deflateSync } from 'node:zlib';
const require = createRequire(import.meta.url);
function chunk(name, data) {
  const type = Buffer.from(name);
  const payload = Buffer.concat([type, data]);
  let crc = 0xffffffff;
  for (const byte of payload) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++)
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  const result = Buffer.alloc(data.length + 12);
  result.writeUInt32BE(data.length);
  payload.copy(result, 4);
  result.writeUInt32BE((crc ^ 0xffffffff) >>> 0, result.length - 4);
  return result;
}
export function inventedPNG() {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(1, 0);
  header.writeUInt32BE(1, 4);
  header[8] = 8;
  header[9] = 6;
  const png = Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', header),
    chunk('IDAT', deflateSync(Buffer.from([0, 255, 0, 0, 255]))),
    chunk('IEND', Buffer.alloc(0)),
  ]);
  return png;
}
export async function inventedGLB(png = inventedPNG(), edit = () => {}) {
  const draco = await require('draco3d').createEncoderModule({});
  const mesh = new draco.Mesh();
  const builder = new draco.MeshBuilder();
  builder.AddFacesToMesh(mesh, 1, new Uint32Array([0, 1, 2]));
  const attribute = builder.AddFloatAttributeToMesh(
    mesh,
    draco.POSITION,
    3,
    3,
    new Float32Array([-100, 0, 0, 100, 0, 0, 0, 100, 0]),
  );
  const uv = builder.AddFloatAttributeToMesh(
    mesh,
    draco.TEX_COORD,
    3,
    2,
    new Float32Array([0, 0, 1, 0, 0, 1]),
  );
  const encoder = new draco.Encoder();
  const output = new draco.DracoInt8Array();
  const length = encoder.EncodeMeshToDracoBuffer(mesh, output);
  assert.ok(length > 0);
  const compressed = Buffer.from(
    Array.from({ length }, (_, i) => output.GetValue(i)),
  );
  for (const obj of [output, encoder, mesh, builder]) draco.destroy(obj);
  const json = {
    asset: {
      version: '2.0',
      generator: 'invented qualification triangle',
      copyright: 'Invented fixture',
    },
    extensionsUsed: ['KHR_draco_mesh_compression'],
    extensionsRequired: ['KHR_draco_mesh_compression'],
    buffers: [
      { byteLength: Math.ceil(compressed.length / 4) * 4 + png.length },
    ],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteLength: compressed.length },
      {
        buffer: 0,
        byteOffset: Math.ceil(compressed.length / 4) * 4,
        byteLength: png.length,
      },
    ],
    images: [{ bufferView: 1, mimeType: 'image/png' }],
    textures: [{ source: 0 }],
    materials: [
      {
        doubleSided: true,
        pbrMetallicRoughness: {
          baseColorTexture: { index: 0 },
          metallicFactor: 0,
          roughnessFactor: 1,
        },
      },
    ],
    accessors: [
      {
        componentType: 5126,
        count: 3,
        type: 'VEC3',
        min: [-100, 0, 0],
        max: [100, 100, 0],
      },
      { componentType: 5123, count: 3, type: 'SCALAR' },
      { componentType: 5126, count: 3, type: 'VEC2' },
    ],
    meshes: [
      {
        primitives: [
          {
            attributes: { POSITION: 0, TEXCOORD_0: 2 },
            material: 0,
            indices: 1,
            mode: 4,
            extensions: {
              KHR_draco_mesh_compression: {
                bufferView: 0,
                attributes: { POSITION: attribute, TEXCOORD_0: uv },
              },
            },
          },
        ],
      },
    ],
    nodes: [{ mesh: 0 }],
    scenes: [{ nodes: [0] }],
    scene: 0,
  };
  edit(json);
  const text = Buffer.from(JSON.stringify(json));
  const padded = Buffer.alloc(Math.ceil(text.length / 4) * 4, 32);
  text.copy(padded);
  const bin = Buffer.alloc(
    Math.ceil((Math.ceil(compressed.length / 4) * 4 + png.length) / 4) * 4,
  );
  compressed.copy(bin);
  png.copy(bin, Math.ceil(compressed.length / 4) * 4);
  const glb = Buffer.alloc(28 + padded.length + bin.length);
  glb.write('glTF');
  glb.writeUInt32LE(2, 4);
  glb.writeUInt32LE(glb.length, 8);
  glb.writeUInt32LE(padded.length, 12);
  glb.writeUInt32LE(0x4e4f534a, 16);
  padded.copy(glb, 20);
  glb.writeUInt32LE(bin.length, 20 + padded.length);
  glb.writeUInt32LE(0x004e4942, 24 + padded.length);
  bin.copy(glb, 28 + padded.length);
  return glb;
}
