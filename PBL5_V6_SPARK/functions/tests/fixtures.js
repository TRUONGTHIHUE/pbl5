'use strict';
const {tokenHash} = require('../validation');
const TOKEN = 'SIMULATED_DEVICE_TOKEN_FOR_UNIT_TESTS_123456789';
function memoryRepository() {
  const stores = {
    'shop-a': {storeName: 'Shop A', ownerUid: 'owner-a', rfidId: 'CD4B1E03', wifiSSID: 'TEST_NETWORK', wifiPassword: 'TEST_PASSWORD_123'},
    'shop-b': {storeName: 'Shop B', ownerUid: 'owner-b', rfidId: 'C79A0C03', wifiSSID: 'TEST_NETWORK', wifiPassword: 'TEST_PASSWORD_123'}
  };
  const devices = {'scanner-test': {enabled: true, tokenSha256: tokenHash(TOKEN)}};
  const allowed = new Set(['shop-a/scanner-test', 'shop-b/scanner-test']);
  const products = {
    'shop-a': [{id: 'a-product', data: {barcode: '00123456', name: 'Only Shop A', price: 100}}],
    'shop-b': [{id: 'b-product', data: {barcode: '00123456', name: 'Only Shop B', price: 200}}]
  };
  return {stores, devices, allowed, products,
    async getDevice(id) { return devices[id] || null; },
    async getStore(id) { return stores[id] || null; },
    async authorized(s, d) { return allowed.has(s + '/' + d); },
    async findStoresByRfid(uid, n) { return Object.entries(stores).filter(([, d]) => d.rfidId === uid).slice(0, n).map(([id, data]) => ({id, data})); },
    async findProducts(s, code, n) { return (products[s] || []).filter(p => p.data.barcode === code).slice(0, n); }
  };
}
function request(action, fields = {}, token = TOKEN) {
  return {method: 'POST', headers: {'x-device-id': 'scanner-test', authorization: 'Bearer ' + token},
          body: {api_version: 2, action, ...fields}};
}
module.exports = {memoryRepository, request, TOKEN};
