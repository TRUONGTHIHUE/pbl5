'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const {firestoreRepository}=require('../firestore_repository');
function fakeDb() {
  const queries=[];
  function node(path=[], clauses=[]) {
    return {
      collection(n){return node([...path,n],clauses);},
      doc(n){return node([...path,n],clauses);},
      where(...args){return node(path,[...clauses,['where',...args]]);},
      limit(n){return node(path,[...clauses,['limit',n]]);},
      async get(){queries.push({path,clauses});return {exists:true,get:k=>k==='enabled',data:()=>({enabled:true}),docs:[]};}
    };
  }
  return {db:node(),queries};
}
test('Firestore adapter scopes products to selected store and preserves barcode type',async()=>{
  const {db,queries}=fakeDb();const repo=firestoreRepository(db);
  await repo.findProducts('shop-a','00123456',2);await repo.findProducts('shop-b','00123456',2);
  assert.deepEqual(queries[0].path,['stores','shop-a','products']);
  assert.deepEqual(queries[1].path,['stores','shop-b','products']);
  assert.deepEqual(queries[0].clauses,[['where','barcode','==','00123456'],['limit',2]]);
});
test('Firestore adapter checks device and per-store grant documents',async()=>{
  const {db,queries}=fakeDb();const repo=firestoreRepository(db);
  await repo.getDevice('scanner-test');assert.ok(await repo.authorized('shop-a','scanner-test'));
  assert.deepEqual(queries[0].path,['devices','scanner-test']);
  assert.deepEqual(queries[1].path,['stores','shop-a','authorizedDevices','scanner-test']);
});
test('Firestore adapter exact canonical RFID query limits to two to detect duplicates',async()=>{
  const {db,queries}=fakeDb();await firestoreRepository(db).findStoresByRfid('CD4B1E03',2);
  assert.deepEqual(queries[0].path,['stores']);
  assert.deepEqual(queries[0].clauses,[['where','rfidId','==','CD4B1E03'],['limit',2]]);
});
