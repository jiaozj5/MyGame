// Large population saves use IndexedDB; old localStorage saves stay untouched.
const DB='fusheng-life', STORE='saves';
let opening;
function database(){
  if(!opening)opening=new Promise((resolve,reject)=>{
    const request=indexedDB.open(DB,1);
    request.onupgradeneeded=()=>request.result.createObjectStore(STORE);
    request.onsuccess=()=>resolve(request.result);
    request.onerror=()=>reject(request.error);
    request.onblocked=()=>reject(new Error('存档数据库暂时被另一个页面占用。'));
  }).catch(error=>{opening=null;throw error;});
  return opening;
}
async function get(key){
  const db=await database();return new Promise((resolve,reject)=>{
    const request=db.transaction(STORE,'readonly').objectStore(STORE).get(key);
    request.onsuccess=()=>resolve(request.result||null);request.onerror=()=>reject(request.error);
  });
}
async function put(key,value){
  const db=await database();return new Promise((resolve,reject)=>{
    const transaction=db.transaction(STORE,'readwrite');transaction.objectStore(STORE).put(value,key);
    transaction.oncomplete=()=>resolve();transaction.onerror=()=>reject(transaction.error);
    transaction.onabort=()=>reject(transaction.error||new Error('自动保存中断。'));
  });
}
export async function storeSave(key,data){
  const value={savedAt:Date.now(),data};
  try{await put(key,value);try{localStorage.removeItem(key);}catch{}}
  catch{localStorage.setItem(key,JSON.stringify(value));}
}
export async function loadSave(key){
  let indexed=null,local=null;
  try{indexed=await get(key);}catch{}
  try{const text=localStorage.getItem(key);if(text)local=JSON.parse(text);}catch{}
  const latest=local&&(!indexed||local.savedAt>indexed.savedAt)?local:indexed;
  return latest?.data||null;
}
