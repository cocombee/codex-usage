// Renderer-local portal targets, scoped to the selected host and chat.
const slots=new Map(), listeners=new Map();
const keyFor=(host,thread)=>JSON.stringify([host,thread]);
export function setDiffSlot(host,thread,node) {
  const key=keyFor(host,thread);
  if(slots.get(key)===node || !node&&!slots.has(key)) return;
  if(node) slots.set(key,node); else slots.delete(key);
  for(const callback of listeners.get(key)??[]) callback();
}
export function readDiffSlot(host,thread) {return slots.get(keyFor(host,thread))??null;}
export function subscribeDiffSlot(host,thread,callback) {
  const key=keyFor(host,thread), callbacks=listeners.get(key)??new Set();
  callbacks.add(callback);listeners.set(key,callbacks);
  return ()=>{callbacks.delete(callback);if(!callbacks.size)listeners.delete(key);};
}
export function useDiffSlot(React,host,thread) {
  const subscribe=React.useCallback(callback=>subscribeDiffSlot(host,thread,callback),[host,thread]);
  const snapshot=React.useCallback(()=>readDiffSlot(host,thread),[host,thread]);
  return React.useSyncExternalStore(subscribe,snapshot,()=>null);
}
