'use strict';
// Default is READ ONLY. Requires admin ADC on the ADMIN machine, never on ESP32/scanner PC.
const {parseArgs} = require('node:util');
const {planRfid, auditBarcodes} = require('../data_audit');
async function main() {
  const {values: opts} = parseArgs({options: {
    project: {type: 'string'}, apply: {type: 'boolean', default: false},
    'confirm-project': {type: 'string'}, 'check-products': {type: 'boolean', default: false}
  }});
  if (!opts.project) throw new Error('Use --project PROJECT_ID. Default: read only.');
  if (opts.apply && opts['confirm-project'] !== opts.project)
    throw new Error('Apply requires --apply --confirm-project PROJECT_ID; backup first.');
  const {initializeApp, applicationDefault} = require('firebase-admin/app');
  const {getFirestore} = require('firebase-admin/firestore');
  initializeApp({projectId: opts.project, credential: applicationDefault()});
  const db = getFirestore();
  // Select only RFID: no Wi-Fi passwords are loaded or printed by this tool.
  const stores = await db.collection('stores').select('rfidId').get();
  const plan = planRfid(stores.docs.map(s => ({id: s.id, rfidId: s.get('rfidId')})));
  console.log(JSON.stringify({project: opts.project, mode: opts.apply ? 'apply' : 'read_only', ...plan}, null, 2));
  if (opts['check-products']) {
    for (const store of stores.docs) {
      const products = await store.ref.collection('products').select('barcode').get();
      console.log(JSON.stringify({store_id: store.id, ...auditBarcodes(products.docs.map(s => ({id: s.id, barcode: s.get('barcode')})))}));
    }
  }
  if (!opts.apply) return;
  if (!plan.safe_to_apply) throw new Error('REFUSED: fix invalid/duplicate RFID before applying any update.');
  const snapshots = new Map(stores.docs.map(s => [s.id, s]));
  // Per-write preconditions avoid overwriting concurrent changes. Multi-batch updates are NOT globally atomic.
  for (let index = 0; index < plan.updates.length; index += 400) {
    const batch = db.batch();
    for (const change of plan.updates.slice(index, index + 400)) {
      const snapshot = snapshots.get(change.id);
      batch.update(snapshot.ref, {rfidId: change.after}, {lastUpdateTime: snapshot.updateTime});
    }
    await batch.commit();
  }
  console.log('RFID updates applied. Re-run read-only audit. Numeric barcodes were NOT converted.');
}
if (require.main === module) main().catch(() => {
  // Full SDK errors can contain resource/user data; keep console failures bounded.
  console.error('AUDIT_FAILED: check ADC/IAM/project, duplicates and concurrent edits. No automatic retry.');
  process.exitCode = 1;
});
module.exports = {main};
