'use strict';
// Local test server only. Fake identities/data; never deploy this file.
const http = require('node:http');
const {createApi} = require('../api');
const {memoryRepository} = require('./fixtures');
const api = createApi(memoryRepository(), {projectId: 'test-project'});
const server = http.createServer(async (req, res) => {
  let raw = '';
  for await (const chunk of req) {raw += chunk; if (raw.length > 4096) break;}
  let body;try {body=JSON.parse(raw);}catch{body=null;}
  const response=await api({method:req.method,headers:req.headers,body,bytes:Buffer.byteLength(raw)});
  res.writeHead(response.status, {'Content-Type':'application/json'});res.end(JSON.stringify(response.body));
});
server.listen(0,'127.0.0.1',()=>console.log(JSON.stringify({port:server.address().port})));
