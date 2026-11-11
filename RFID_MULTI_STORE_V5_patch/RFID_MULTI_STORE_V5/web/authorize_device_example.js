// OPTIONAL SAMPLE for your existing owner website (Firebase Web SDK v9+).
// Integrate with your actual auth/db instances; do not deploy this file alone.
import { doc, getDoc, setDoc, deleteDoc } from 'firebase/firestore';

function validId(deviceId) {
  return typeof deviceId === 'string' && /^[A-Za-z0-9_-]{3,64}$/.test(deviceId);
}
async function ensureOwner(db, auth, storeDocumentId) {
  const user = auth.currentUser;
  if (!user) throw new Error('Ban can dang nhap website truoc');
  const snapshot = await getDoc(doc(db, 'stores', storeDocumentId));
  if (!snapshot.exists() || snapshot.data().ownerUid !== user.uid) {
    throw new Error('Ban khong so huu cua hang nay');
  }
}
export async function allowScanner(db, auth, storeDocumentId, deviceId) {
  if (!validId(deviceId)) throw new Error('Ma thiet bi khong hop le');
  await ensureOwner(db, auth, storeDocumentId);
  await setDoc(doc(db, 'stores', storeDocumentId, 'authorizedDevices', deviceId),
               {enabled: true});
}
export async function revokeScanner(db, auth, storeDocumentId, deviceId) {
  if (!validId(deviceId)) throw new Error('Ma thiet bi khong hop le');
  await ensureOwner(db, auth, storeDocumentId);
  await deleteDoc(doc(db, 'stores', storeDocumentId, 'authorizedDevices', deviceId));
}
// The Firestore Rules fragment is what ENFORCES permissions on the server.
// This client-side owner check is only for a friendlier error message.
