'use strict';
function firestoreRepository(db) {
  return {
    async getDevice(id) { const s = await db.collection('devices').doc(id).get(); return s.exists ? s.data() : null; },
    async getStore(id) { const s = await db.collection('stores').doc(id).get(); return s.exists ? s.data() : null; },
    async authorized(storeId, deviceId) {
      const s = await db.collection('stores').doc(storeId).collection('authorizedDevices').doc(deviceId).get();
      return s.exists && s.get('enabled') === true;
    },
    async findStoresByRfid(rfid, limit) {
      const q = await db.collection('stores').where('rfidId', '==', rfid).limit(limit).get();
      return q.docs.map(s => ({id: s.id, data: s.data()}));
    },
    async findProducts(storeId, barcode, limit) {
      const q = await db.collection('stores').doc(storeId).collection('products')
        .where('barcode', '==', barcode).limit(limit).get();
      return q.docs.map(s => ({id: s.id, data: s.data()}));
    }
  };
}
module.exports = {firestoreRepository};
