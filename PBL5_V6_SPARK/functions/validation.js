'use strict';
const crypto = require('node:crypto');
const API_VERSION = 2;
function normalizeRfid(value) {
  if (typeof value !== 'string') return null;
  const s = value.replace(/[\s:-]/g, '').toUpperCase();
  return /^(?:[A-F0-9]{8}|[A-F0-9]{14}|[A-F0-9]{20})$/.test(s) ? s : null;
}
function text(value, maxBytes, allowEmpty = false) {
  return typeof value === 'string' && (allowEmpty || value.length > 0) &&
    Buffer.byteLength(value, 'utf8') <= maxBytes && !/[\x00-\x1f\x7f]/.test(value);
}
function storeId(value) {
  return text(value, 255) && !value.includes('/') && value !== '.' && value !== '..';
}
function wifi(ssid, password) {
  return text(ssid, 32) && typeof password === 'string' &&
    (password === '' || /^[\x20-\x7e]{8,63}$/.test(password) || /^[a-fA-F0-9]{64}$/.test(password));
}
function tokenHash(token) { return crypto.createHash('sha256').update(token, 'utf8').digest('hex'); }
function validTokenHash(hash, token) {
  return typeof hash === 'string' && /^[a-fA-F0-9]{64}$/.test(hash) &&
    crypto.timingSafeEqual(Buffer.from(hash, 'hex'), Buffer.from(tokenHash(token), 'hex'));
}
function credentials(headers) {
  const id = headers['x-device-id'];
  const bearer = /^Bearer ([A-Za-z0-9_-]{32,128})$/i.exec(headers.authorization || '');
  return typeof id === 'string' && /^[A-Za-z0-9_-]{3,64}$/.test(id) && bearer
    ? {id, token: bearer[1]} : null;
}
module.exports = {API_VERSION, normalizeRfid, text, storeId, wifi, tokenHash, validTokenHash, credentials};
