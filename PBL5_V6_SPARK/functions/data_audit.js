'use strict';
const {normalizeRfid} = require('./validation');
function planRfid(documents) {
  const seen = new Map(), updates = [], invalid = [];
  for (const {id, rfidId} of documents) {
    const canonical = normalizeRfid(rfidId);
    if (!canonical) { invalid.push({id, code: 'invalid_or_missing_rfid'}); continue; }
    if (!seen.has(canonical)) seen.set(canonical, []);
    seen.get(canonical).push(id);
    if (canonical !== rfidId) updates.push({id, before: rfidId, after: canonical});
  }
  const duplicates = [...seen].filter(([, ids]) => ids.length > 1).map(([rfid, ids]) => ({rfid, ids}));
  return {updates, invalid, duplicates, safe_to_apply: invalid.length === 0 && duplicates.length === 0};
}
function auditBarcodes(products) {
  const invalid = [], map = new Map();
  for (const {id, barcode} of products) {
    if (typeof barcode !== 'string' || barcode.length === 0) { invalid.push(id); continue; }
    if (!map.has(barcode)) map.set(barcode, []);
    map.get(barcode).push(id);
  }
  return {invalid, duplicates: [...map].filter(([, ids]) => ids.length > 1).map(([barcode, ids]) => ({barcode, ids}))};
}
module.exports = {planRfid, auditBarcodes};
