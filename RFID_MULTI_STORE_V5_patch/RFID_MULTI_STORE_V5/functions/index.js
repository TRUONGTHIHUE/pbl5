'use strict';
// An authenticated server endpoint. NEVER use Admin SDK inside PC/ESP firmware.
const {onRequest} = require('firebase-functions/v2/https');
const {logger} = require('firebase-functions');
const admin = require('firebase-admin');
const {normalizeRfid, validStoreId, validWifi, equalHash, tokenFromHeader} = require('./api_helpers');
admin.initializeApp();
const db = admin.firestore();

function reply(res, status, code, extra = {}) {
  return res.status(status).json({ok: false, code, ...extra});
}
async function getDevice(req) {
  const deviceId = req.header('x-device-id');
  const token = tokenFromHeader(req.header('authorization'));
  if (!deviceId || !/^[A-Za-z0-9_-]{3,64}$/.test(deviceId) || !token) return null;
  const snapshot = await db.collection('devices').doc(deviceId).get();
  if (!snapshot.exists || snapshot.get('enabled') !== true ||
      !equalHash(snapshot.get('tokenSha256'), token)) return null;
  return {deviceId};
}
async function storePermitted(storeId, deviceId) {
  const permitted = await db.collection('stores').doc(storeId)
    .collection('authorizedDevices').doc(deviceId).get();
  return permitted.exists && permitted.get('enabled') === true;
}
function storeEnabled(doc) {
  // For compatibility with existing data: absent 'enabled' is treated as enabled.
  return doc.get('enabled') !== false;
}

exports.deviceApi = onRequest({
  region: 'asia-southeast1',
  cors: false,
  maxInstances: 2,
  timeoutSeconds: 30,
  memory: '256MiB',
}, async (req, res) => {
  res.set('Cache-Control', 'no-store');
  if (req.method !== 'POST') return reply(res, 405, 'method_not_allowed');
  if (!req.is('application/json') || !req.body || typeof req.body !== 'object' ||
      Array.isArray(req.body)) return reply(res, 400, 'invalid_json');
  try {
    const device = await getDevice(req);
    if (!device) return reply(res, 401, 'device_not_authenticated');
    const action = req.body.action;
    if (action === 'ping') return res.json({ok: true, deviceId: device.deviceId});

    if (action === 'resolve_store') {
      const rfid = normalizeRfid(req.body.rfid_uid);
      if (!rfid) return reply(res, 400, 'invalid_rfid');
      // The rfidId field in Firestore MUST be normalized uppercase without separators.
      const matches = await db.collection('stores').where('rfidId', '==', rfid).limit(2).get();
      if (matches.empty) return reply(res, 404, 'store_not_found');
      if (matches.size !== 1) return reply(res, 409, 'duplicate_rfid');
      const store = matches.docs[0];
      if (!storeEnabled(store) || !await storePermitted(store.id, device.deviceId))
        return reply(res, 404, 'store_not_found_or_not_authorized');
      const ssid = store.get('wifiSSID');
      const password = store.get('wifiPassword');
      const storeName = store.get('storeName') || 'Cua hang';
      if (!validWifi(ssid, password) || typeof storeName !== 'string' ||
          Buffer.byteLength(storeName, 'utf8') > 255 || !validStoreId(store.id))
        return reply(res, 422, 'store_wifi_configuration_invalid');
      // Only an authenticated, explicitly authorized device sees the Wi-Fi secret.
      return res.json({ok: true, store_id: store.id, store_name: storeName,
                       ssid, password});
    }

    if (action === 'lookup_product') {
      const storeId = req.body.store_id;
      const barcode = req.body.barcode;
      if (!validStoreId(storeId) || typeof barcode !== 'string' ||
          barcode.length < 1 || Buffer.byteLength(barcode, 'utf8') > 128)
        return reply(res, 400, 'invalid_product_query');
      const store = await db.collection('stores').doc(storeId).get();
      if (!store.exists || !storeEnabled(store) ||
          !await storePermitted(storeId, device.deviceId))
        return reply(res, 404, 'store_not_found_or_not_authorized');
      const products = await db.collection('stores').doc(storeId).collection('products')
        .where('barcode', '==', barcode).limit(2).get();
      if (products.empty) return res.json({ok: true, status: 'not_found', fields: {}});
      if (products.size > 1) return res.json({ok: true, status: 'duplicate', fields: {}});
      const fields = products.docs[0].data();
      if (Buffer.byteLength(JSON.stringify(fields), 'utf8') > 20000)
        return reply(res, 422, 'product_response_too_large');
      return res.json({ok: true, status: 'found', fields});
    }
    return reply(res, 400, 'unknown_action');
  } catch (error) {
    // Never log request body, device secret, Wi-Fi password or full credentials.
    logger.error('deviceApi failed', {code: error.code || 'internal'});
    return reply(res, 500, 'internal_error');
  }
});
