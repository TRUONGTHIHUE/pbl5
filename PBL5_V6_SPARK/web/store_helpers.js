/* Integration example, NOT an already-integrated website. Requires Firebase Web SDK. */
import {doc, getDoc, updateDoc, setDoc} from 'firebase/firestore';
export function canonicalRfid(value) {
  if (typeof value !== 'string') throw new Error('RFID must be a string');
  const uid=value.replace(/[\s:-]/g,'').toUpperCase();
  if (!/^(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})$/.test(uid)) throw new Error('Invalid RFID');
  return uid;
}
export async function saveStoreWifi(db, auth, storeId, {rfidId,wifiSSID,wifiPassword}) {
  if (!auth.currentUser) throw new Error('Sign in on website first');
  const ref=doc(db,'stores',storeId);const store=await getDoc(ref);
  if (!store.exists() || store.data().ownerUid!==auth.currentUser.uid) throw new Error('Not store owner');
  const size=new TextEncoder().encode(wifiSSID).length;
  if (typeof wifiSSID!=='string'||size<1||size>32||/[\x00-\x1f\x7f]/.test(wifiSSID)) throw new Error('Invalid SSID');
  if (typeof wifiPassword!=='string'||!(wifiPassword===''||/^[\x20-\x7e]{8,63}$/.test(wifiPassword)||/^[0-9a-fA-F]{64}$/.test(wifiPassword))) throw new Error('Invalid password format');
  await updateDoc(ref,{rfidId:canonicalRfid(rfidId),wifiSSID,wifiPassword});
  // No console.log of credentials. UI checks do not replace Firestore Rules.
  // Uniqueness across owners is verified by the backend/data audit; do not make stores public.
}
export async function setScannerPermission(db, auth, storeId, deviceId, enabled) {
  if (!auth.currentUser || !/^[A-Za-z0-9_-]{3,64}$/.test(deviceId)||typeof enabled!=='boolean') throw new Error('Invalid request');
  const store=await getDoc(doc(db,'stores',storeId));
  if (!store.exists()||store.data().ownerUid!==auth.currentUser.uid) throw new Error('Not store owner');
  await setDoc(doc(db,'stores',storeId,'authorizedDevices',deviceId),{enabled});
}
