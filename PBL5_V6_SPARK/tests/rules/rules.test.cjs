const {initializeTestEnvironment,assertSucceeds,assertFails}=require('@firebase/rules-unit-testing');
const {doc,setDoc,getDoc,getDocs,collection,query,where,updateDoc}=require('firebase/firestore');
const fs=require('node:fs');const assert=require('node:assert/strict');
(async()=>{
 const env=await initializeTestEnvironment({projectId:'demo-pbl5-spark',firestore:{host:'127.0.0.1',port:18085,rules:fs.readFileSync(require('node:path').resolve(__dirname,'../../firestore.spark.rules.example'),'utf8')}});
 let count=0;
 try{
 await env.withSecurityRulesDisabled(async context=>{
 const db=context.firestore();
 for(const [path,data] of Object.entries({
 'devices/scanner1':{enabled:true},
 'stores/a':{ownerUid:'ownerA',rfidId:'C79A0C03',wifiSSID:'SameWifi',wifiPassword:'fake-password'},
 'stores/b':{ownerUid:'ownerB',rfidId:'11223344',wifiSSID:'SameWifi',wifiPassword:'fake-password'},
 'stores/c':{ownerUid:'ownerC',rfidId:'AABBCCDD'},
 'stores/a/authorizedDevices/scanner1':{enabled:true},'stores/b/authorizedDevices/scanner1':{enabled:true},
 'rfidStores/C79A0C03':{storeId:'a'},'rfidStores/11223344':{storeId:'b'},'rfidStores/AABBCCDD':{storeId:'c'},
 'stores/a/products/p1':{barcode:'00123',name:'ProductA'},'stores/b/products/p1':{barcode:'00123',name:'ProductB'}
 }))await setDoc(doc(db,path),data);
 });
 const s=env.authenticatedContext('scanner1').firestore(), anon=env.unauthenticatedContext().firestore();
 const owner=env.authenticatedContext('ownerA').firestore(),stranger=env.authenticatedContext('other').firestore();
 async function yes(p){await assertSucceeds(p);count++}async function no(p){await assertFails(p);count++}
 await yes(getDoc(doc(s,'devices/scanner1')));
 await no(getDoc(doc(anon,'stores/a')));await no(getDoc(doc(stranger,'stores/a')));
 await yes(getDoc(doc(s,'rfidStores/C79A0C03')));await yes(getDoc(doc(s,'stores/a')));
 await no(getDocs(collection(s,'rfidStores')));await no(getDocs(collection(s,'stores')));
 await no(getDoc(doc(s,'rfidStores/AABBCCDD')));await no(getDoc(doc(s,'stores/c')));
 const qa=await assertSucceeds(getDocs(query(collection(s,'stores/a/products'),where('barcode','==','00123'))));
 const qb=await assertSucceeds(getDocs(query(collection(s,'stores/b/products'),where('barcode','==','00123'))));
 assert.equal(qa.docs[0].data().name,'ProductA');assert.equal(qb.docs[0].data().name,'ProductB');count+=2;
 await no(setDoc(doc(s,'devices/scanner1'),{enabled:true}));
 await no(setDoc(doc(s,'rfidStores/C79A0C03'),{storeId:'b'}));
 await no(setDoc(doc(s,'stores/a/products/hack'),{barcode:'hacked'}));
 await yes(getDocs(query(collection(owner,'stores'),where('ownerUid','==','ownerA'))));
 await yes(setDoc(doc(owner,'stores/a/products/p2'),{barcode:'00999',name:'New'}));
 await no(setDoc(doc(owner,'stores/a/products/p3'),{barcode:123}));
 await no(updateDoc(doc(owner,'stores/a'),{ownerUid:'other'}));
 await no(setDoc(doc(stranger,'stores/a/authorizedDevices/other'),{enabled:true}));
 await yes(updateDoc(doc(owner,'stores/a/authorizedDevices/scanner1'),{enabled:false}));
 await no(getDoc(doc(s,'stores/a')));await no(getDocs(query(collection(s,'stores/a/products'),where('barcode','==','00123'))));
 await no(getDoc(doc(s,'rfidStores/C79A0C03')));
 await env.withSecurityRulesDisabled(async c=>updateDoc(doc(c.firestore(),'devices/scanner1'),{enabled:false}));
 await no(getDoc(doc(s,'stores/b')));
 console.log('PASS '+count+' Firestore Emulator checks; no live project accessed.');
 }finally{await env.cleanup()}
})().catch(e=>{console.error(e);process.exitCode=1});
