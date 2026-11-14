'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const {createApi} = require('../api');
const {memoryRepository, request} = require('./fixtures');
const {normalizeRfid, wifi} = require('../validation');
const {planRfid, auditBarcodes} = require('../data_audit');
function setup() { const repo = memoryRepository(); return {repo, api: createApi(repo, {projectId: 'test-project'})}; }
test('auth and API version are required', async () => {
  const {api} = setup();
  assert.equal((await api(request('ping', {}, 'wrong'))).status, 401);
  assert.equal((await api({...request('ping'), body: {action: 'ping'}})).status, 426);
  assert.equal((await api(request('ping'))).body.project_id, 'test-project');
});
test('disabled device is rejected', async () => {
  const {repo, api} = setup(); repo.devices['scanner-test'].enabled = false;
  assert.equal((await api(request('ping'))).status, 401);
});
test('valid RFID accepts separators and returns owner identity', async () => {
  const {api} = setup(); const r = await api(request('resolve_store', {rfid_uid: 'cd 4b 1e 03'}));
  assert.equal(r.status, 200); assert.equal(r.body.store.id, 'shop-a');
  assert.equal(r.body.store.owner_uid, 'owner-a'); assert.equal(r.body.store.rfid_uid, 'CD4B1E03');
});
test('malformed and non-existing RFID', async () => {
  const {api} = setup();
  assert.equal((await api(request('resolve_store', {rfid_uid: 1234}))).status, 400);
  assert.equal((await api(request('resolve_store', {rfid_uid: 'DEADBEEF'}))).body.code, 'store_not_found');
});
test('RFID duplicate across owners is rejected', async () => {
  const {repo, api} = setup(); repo.stores['shop-b'].rfidId = 'CD4B1E03';
  assert.equal((await api(request('resolve_store', {rfid_uid: 'CD4B1E03'}))).body.code, 'duplicate_rfid');
});
test('RFID alone is insufficient: unauthorized scanner never receives Wi-Fi', async () => {
  const {repo, api} = setup(); repo.allowed.clear();
  const r = await api(request('resolve_store', {rfid_uid: 'CD4B1E03'}));
  assert.equal(r.status, 403); assert.equal(r.body.wifi, undefined);
});
test('two stores sharing Wi-Fi preserve different store/owner IDs', async () => {
  const {api} = setup();
  const a = (await api(request('resolve_store', {rfid_uid: 'CD4B1E03'}))).body;
  const b = (await api(request('resolve_store', {rfid_uid: 'C79A0C03'}))).body;
  assert.deepEqual(a.wifi, b.wifi); assert.notEqual(a.store.id, b.store.id);
});
test('two stores with same string barcode return their own product', async () => {
  const {api} = setup();
  const a = (await api(request('lookup_product', {store_id: 'shop-a', barcode: '00123456'}))).body;
  const b = (await api(request('lookup_product', {store_id: 'shop-b', barcode: '00123456'}))).body;
  assert.equal(a.fields.name, 'Only Shop A'); assert.equal(b.fields.name, 'Only Shop B');
  assert.equal(a.barcode, '00123456'); assert.equal(a.fields.barcode, '00123456');
});
test('numeric barcode is rejected, never silently converted', async () => {
  const {api} = setup(); assert.equal((await api(request('lookup_product', {store_id: 'shop-a', barcode: 123456}))).status, 400);
});
test('missing barcode only searches selected store', async () => {
  const {repo, api} = setup(); repo.products['shop-b'].push({id: 'unique', data: {barcode: 'ONLYB'}});
  const r = await api(request('lookup_product', {store_id: 'shop-a', barcode: 'ONLYB'}));
  assert.equal(r.body.status, 'not_found'); assert.deepEqual(r.body.fields, {});
});
test('duplicate barcode in ONE store returns duplicate, not arbitrary product', async () => {
  const {repo, api} = setup(); repo.products['shop-a'].push({id: 'dup', data: {barcode: '00123456'}});
  assert.equal((await api(request('lookup_product', {store_id: 'shop-a', barcode: '00123456'}))).body.status, 'duplicate');
});
test('revoked store permission also blocks products', async () => {
  const {repo, api} = setup(); repo.allowed.delete('shop-a/scanner-test');
  assert.equal((await api(request('lookup_product', {store_id: 'shop-a', barcode: '00123456'}))).status, 403);
});
test('invalid Wi-Fi and missing owner are explicit configuration errors', async () => {
  const {repo, api} = setup(); repo.stores['shop-a'].wifiPassword = 'short';
  assert.equal((await api(request('resolve_store', {rfid_uid: 'CD4B1E03'}))).status, 422);
  repo.stores['shop-a'].wifiPassword = 'ValidExample123'; delete repo.stores['shop-a'].ownerUid;
  assert.equal((await api(request('resolve_store', {rfid_uid: 'CD4B1E03'}))).status, 422);
});
test('invalid paths, request method and size are rejected', async () => {
  const {api} = setup();
  assert.equal((await api(request('lookup_product', {store_id: '../shop-a', barcode: 'x'}))).status, 400);
  assert.equal((await api({...request('ping'), method: 'GET'})).status, 405);
  assert.equal((await api({...request('ping'), bytes: 4097})).status, 413);
});
test('backend exceptions produce bounded redacted errors', async () => {
  const {repo} = setup(); const logs = []; repo.getDevice = async () => { throw new Error('SECRET_IN_SDK_ERROR'); };
  const r = await createApi(repo, {logError: c => logs.push(c)})(request('ping'));
  assert.equal(r.status, 500); assert.ok(!JSON.stringify({r, logs}).includes('SECRET_IN_SDK_ERROR'));
});
test('RFID supports 4/7/10 bytes, not a single hardcoded card', () => {
  for (const uid of ['CD4B1E03', 'C79A0C03', '01020304050607', '0102030405060708090A']) assert.equal(normalizeRfid(uid), uid);
  assert.equal(normalizeRfid('123'), null);
});
test('Wi-Fi validation includes byte limits/open/hex PSK', () => {
  assert.ok(wifi('TEST', 'Password123')); assert.ok(wifi('TEST', ''));
  assert.ok(wifi('TEST', 'a'.repeat(64))); assert.ok(!wifi('TEST', 'z'.repeat(64)));
  assert.ok(!wifi('x'.repeat(33), 'Password123')); assert.ok(!wifi('TEST', 'bad\u0000pass'));
});
test('migration catches canonical collisions before any writes', () => {
  const p = planRfid([{id: 'a', rfidId: 'CD 4B 1E 03'}, {id: 'b', rfidId: 'cd:4b:1e:03'}]);
  assert.equal(p.safe_to_apply, false); assert.equal(p.duplicates[0].rfid, 'CD4B1E03');
});
test('migration plans spaced UID normalization and flags numeric barcode', () => {
  const p = planRfid([{id: 'known', rfidId: 'CD 4B 1E 03'}]);
  assert.ok(p.safe_to_apply); assert.equal(p.updates[0].after, 'CD4B1E03');
  const b = auditBarcodes([{id: 'a', barcode: 1234}, {id: 'b', barcode: '001234'}]);
  assert.deepEqual(b.invalid, ['a']);
});
test('noncanonical stored RFID is not silently full-scanned; audit required', async () => {
  const {repo, api} = setup(); repo.stores['shop-a'].rfidId = 'CD 4B 1E 03';
  assert.equal((await api(request('resolve_store', {rfid_uid: 'CD4B1E03'}))).body.code, 'store_not_found');
});
