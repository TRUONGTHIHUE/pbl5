'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const helpers = require('../api_helpers');

function fakeDb() {
  const docs = new Map();
  function reference(path) {
    const id = path.split('/').at(-1);
    return {
      id,
      get: async () => {
        const value = docs.get(path);
        return { id, exists: value !== undefined,
                 get: (name) => value?.[name], data: () => value };
      },
      collection: (name) => collection(`${path}/${name}`),
    };
  }
  function collection(path) {
    return {
      doc: (id) => reference(`${path}/${id}`),
      where: (field, op, val) => {
        assert.equal(op, '==');
        return { limit: (n) => ({ get: async () => {
          const matches = [...docs.entries()]
            .filter(([p, data]) => p.startsWith(`${path}/`) &&
              p.split('/').length === path.split('/').length + 1 && data[field] === val)
            .slice(0, n)
            .map(([p, data]) => ({id: p.split('/').at(-1), get: (f) => data[f], data: () => data}));
          return {empty: !matches.length, size: matches.length, docs: matches};
        }})};
      },
    };
  }
  return {docs, collection};
}
const database = fakeDb();
const originalLoad = Module._load;
let handler;
try {
  Module._load = function(name, ...rest) {
    if (name === 'firebase-admin') return {initializeApp() {}, firestore: () => database};
    if (name === 'firebase-functions/v2/https') return {onRequest: (options, fn) => fn};
    if (name === 'firebase-functions') return {logger: {error() {}}};
    return originalLoad.call(this, name, ...rest);
  };
  handler = require('../index').deviceApi;
} finally {
  Module._load = originalLoad;
}

const TOKEN = 'A'.repeat(43);
const ID = 'pc-test-01';
database.docs.set(`devices/${ID}`, {enabled: true, tokenSha256: helpers.hashToken(TOKEN)});
database.docs.set('stores/shop-a', {ownerUid: 'owner-a', rfidId: 'C79A0C03',
  storeName: 'Cua hang A', wifiSSID: 'WiFi_A', wifiPassword: 'PasswordA123'});
database.docs.set('stores/shop-a/products/prod-1', {barcode: '123456', name: 'Gao', price: 10000});

async function call(action, body = {}, token = TOKEN) {
  const req = {method: 'POST', body: {action, ...body},
    is: (type) => type === 'application/json',
    header: (name) => ({'x-device-id': ID, 'authorization': 'Bearer ' + token})[name]};
  const res = {statusCode: 200, set() {return this;}, status(code) {this.statusCode=code;return this;},
    json(data) {this.body=data;return this;}};
  await handler(req, res);
  return res;
}

test('only authenticated device can ping', async () => {
  assert.equal((await call('ping')).body.deviceId, ID);
  assert.equal((await call('ping', {}, 'B'.repeat(43))).statusCode, 401);
});
test('RFID alone is not enough; device must be approved by store', async () => {
  const absent = await call('resolve_store', {rfid_uid: 'C79A0C03'});
  assert.equal(absent.statusCode, 404);
  database.docs.set(`stores/shop-a/authorizedDevices/${ID}`, {enabled: true});
  const result = await call('resolve_store', {rfid_uid: 'c7:9a:0c:03'});
  assert.equal(result.statusCode, 200);
  assert.equal(result.body.store_id, 'shop-a');
  assert.equal(result.body.password, 'PasswordA123');
});
test('product lookup also checks the device store permission', async () => {
  const found = await call('lookup_product', {store_id: 'shop-a', barcode: '123456'});
  assert.equal(found.body.status, 'found');
  assert.equal(found.body.fields.name, 'Gao');
  const missed = await call('lookup_product', {store_id: 'shop-a', barcode: 'missing'});
  assert.equal(missed.body.status, 'not_found');
  const denied = await call('lookup_product', {store_id: 'shop-b', barcode: '123456'});
  assert.equal(denied.statusCode, 404);
});
test('duplicate RFID is rejected', async () => {
  database.docs.set('stores/shop-b', {rfidId: 'C79A0C03', wifiSSID: 'WiFi_B', wifiPassword: 'PasswordB123'});
  const result = await call('resolve_store', {rfid_uid: 'C79A0C03'});
  assert.equal(result.statusCode, 409);
});
