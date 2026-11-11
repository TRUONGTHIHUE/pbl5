const test = require('node:test');
const assert = require('node:assert/strict');
const h = require('../api_helpers');
test('normalizeRfid', () => {
  assert.equal(h.normalizeRfid('c7:9a:0c:03'), 'C79A0C03');
  assert.equal(h.normalizeRfid('A1B2C3'), null);
});
test('Wi-Fi validation', () => {
  assert.equal(h.validWifi('Shop_A', '12345678'), true);
  assert.equal(h.validWifi('Shop_A', ''), true);
  assert.equal(h.validWifi('Shop_A', 'short'), false);
  assert.equal(h.validWifi('x'.repeat(33), '12345678'), false);
});
test('token constant time compare', () => {
  const token = 'q'.repeat(43);
  assert.equal(h.equalHash(h.hashToken(token), token), true);
  assert.equal(h.equalHash(h.hashToken(token), 'x'.repeat(43)), false);
  assert.equal(h.tokenFromHeader('Bearer ' + token), token);
  assert.equal(h.tokenFromHeader('Bearer short'), null);
});
test('store IDs never allow path traversal', () => {
  assert.equal(h.validStoreId('shop-01'), true);
  assert.equal(h.validStoreId('a/b'), false);
  assert.equal(h.validStoreId('..'), false);
});
