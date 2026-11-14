'use strict';
const V = require('./validation');
/** Pure application service; the Firebase adapter and tests use this SAME code. */
function createApi(repo, {projectId = '', logError = () => {}} = {}) {
  const ok = (data = {}) => ({status: 200, body: {ok: true, api_version: V.API_VERSION, ...data}});
  const fail = (status, code) => ({status, body: {ok: false, api_version: V.API_VERSION, code}});
  return async function handle({method = 'POST', headers = {}, body, bytes = 0}) {
    if (method !== 'POST') return fail(405, 'method_not_allowed');
    if (bytes > 4096) return fail(413, 'request_too_large');
    if (!body || typeof body !== 'object' || Array.isArray(body)) return fail(400, 'invalid_json');
    if (body.api_version !== V.API_VERSION) return fail(426, 'api_version_mismatch');
    try {
      const auth = V.credentials(headers);
      if (!auth) return fail(401, 'device_not_authenticated');
      const device = await repo.getDevice(auth.id);
      if (!device || device.enabled !== true || !V.validTokenHash(device.tokenSha256, auth.token))
        return fail(401, 'device_not_authenticated');
      if (body.action === 'ping') return ok({service: 'pbl5-device-api', device_id: auth.id, project_id: projectId});
      if (body.action === 'resolve_store') {
        const rfid = V.normalizeRfid(body.rfid_uid);
        if (!rfid) return fail(400, 'invalid_rfid');
        // Stored rfidId MUST be canonical. Run the read-only data audit before deployment.
        const matches = await repo.findStoresByRfid(rfid, 2);
        if (matches.length === 0) return fail(404, 'store_not_found');
        if (matches.length !== 1) return fail(409, 'duplicate_rfid');
        const store = matches[0], data = store.data;
        if (data.enabled === false || !await repo.authorized(store.id, auth.id))
          return fail(403, 'store_not_authorized');
        if (!V.storeId(store.id) || !V.text(data.storeName, 255) || !V.text(data.ownerUid, 128) ||
            !V.wifi(data.wifiSSID, data.wifiPassword)) return fail(422, 'store_configuration_invalid');
        return ok({store: {id: store.id, name: data.storeName, owner_uid: data.ownerUid, rfid_uid: rfid},
                   wifi: {ssid: data.wifiSSID, password: data.wifiPassword}});
      }
      if (body.action === 'lookup_product') {
        if (!V.storeId(body.store_id) || !V.text(body.barcode, 128)) return fail(400, 'invalid_product_query');
        const store = await repo.getStore(body.store_id);
        // Recheck authorization on EVERY product lookup, including after a Wi-Fi reconnect.
        if (!store || store.enabled === false || !await repo.authorized(body.store_id, auth.id))
          return fail(403, 'store_not_authorized');
        const matches = await repo.findProducts(body.store_id, body.barcode, 2);
        const identity = {store_id: body.store_id, barcode: body.barcode};
        if (matches.length === 0) return ok({...identity, status: 'not_found', fields: {}});
        if (matches.length !== 1) return ok({...identity, status: 'duplicate', fields: {}});
        const product = matches[0];
        const response = {...identity, status: 'found', product_id: product.id, fields: product.data};
        if (Buffer.byteLength(JSON.stringify(response), 'utf8') > 20000)
          return fail(422, 'product_response_too_large');
        return ok(response);
      }
      return fail(400, 'unknown_action');
    } catch (_error) {
      // Do not log bodies, Authorization headers, tokens, passwords or arbitrary SDK messages.
      logError('backend_operation_failed');
      return fail(500, 'internal_error');
    }
  };
}
module.exports = {createApi};
