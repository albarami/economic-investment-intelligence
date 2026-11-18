import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import tls from 'node:tls';

export async function denyNetwork(work) {
  const attempts = [];
  const targets = [
    [globalThis, 'fetch'],
    [http, 'request'],
    [http, 'get'],
    [https, 'request'],
    [https, 'get'],
    [net, 'connect'],
    [net, 'createConnection'],
    [net.Socket.prototype, 'connect'],
    [tls, 'connect'],
  ];
  const originals = targets.map(([object, key]) => object[key]);
  for (const [object, key] of targets)
    object[key] = () => {
      attempts.push(key);
      throw new Error('NETWORK');
    };
  try {
    return await work(attempts);
  } finally {
    for (const [index, [object, key]] of targets.entries())
      object[key] = originals[index];
  }
}
