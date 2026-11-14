'use strict';
const {onRequest} = require('firebase-functions/v2/https');
const {logger} = require('firebase-functions');
const {getApps, initializeApp} = require('firebase-admin/app');
const {getFirestore} = require('firebase-admin/firestore');
const {createApi} = require('./api');
const {firestoreRepository} = require('./firestore_repository');
if (!getApps().length) initializeApp();
const handler = createApi(firestoreRepository(getFirestore()), {
  projectId: process.env.GCLOUD_PROJECT || process.env.GOOGLE_CLOUD_PROJECT || '',
  logError: code => logger.error('device_api_error', {code})
});
// A separate export prevents accidental replacement of the old V5 deviceApi endpoint.
// Cloud IAM allows calling this URL; application-level device auth above is mandatory.
exports.deviceApiV6 = onRequest({region: 'asia-southeast1', invoker: 'public', cors: false,
  timeoutSeconds: 30, memory: '256MiB', minInstances: 0, maxInstances: 2, concurrency: 10},
async (req, res) => {
  res.set('Cache-Control', 'no-store');
  res.set('X-Content-Type-Options', 'nosniff');
  if (!req.is('application/json'))
    return res.status(415).json({ok: false, api_version: 2, code: 'application_json_required'});
  const result = await handler({method: req.method, headers: {
    'x-device-id': req.get('x-device-id'), authorization: req.get('authorization')},
    body: req.body, bytes: req.rawBody ? req.rawBody.length : 0});
  return res.status(result.status).json(result.body);
});
