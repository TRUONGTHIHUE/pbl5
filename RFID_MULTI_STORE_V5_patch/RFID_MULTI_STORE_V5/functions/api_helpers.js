'use strict';
const crypto = require('node:crypto');

function normalizeRfid(value) {
  if (typeof value !== 'string') return null;
  const uid = value.replace(/[\s:-]/g, '').toUpperCase();
  return /^(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})$/.test(uid) ? uid : null;
}
function validStoreId(value) {
  return typeof value === 'string' && Buffer.byteLength(value, 'utf8') > 0 &&
    Buffer.byteLength(value, 'utf8') <= 255 && !value.includes('/') && value !== '.' && value !== '..';
}
function validWifi(ssid, password) {
  if (typeof ssid !== 'string' || typeof password !== 'string') return false;
  const a = Buffer.byteLength(ssid, 'utf8');
  const b = Buffer.byteLength(password, 'utf8');
  return a >= 1 && a <= 32 &&
    (b === 0 || (b >= 8 && b <= 63) || (b === 64 && /^[0-9a-fA-F]{64}$/.test(password)));
}
function hashToken(token) {
  return crypto.createHash('sha256').update(token, 'utf8').digest('hex');
}
function equalHash(expected, supplied) {
  if (typeof expected !== 'string' || !/^[0-9a-fA-F]{64}$/.test(expected)) return false;
  const a = Buffer.from(expected.toLowerCase(), 'hex');
  const b = Buffer.from(hashToken(supplied), 'hex');
  return crypto.timingSafeEqual(a, b);
}
function tokenFromHeader(header) {
  if (typeof header !== 'string') return null;
  const match = /^Bearer ([A-Za-z0-9_-]{32,128})$/i.exec(header);
  return match ? match[1] : null;
}
module.exports = { normalizeRfid, validStoreId, validWifi, hashToken, equalHash, tokenFromHeader };
