// Renderer-local counts/timing only. No text, credentials or persistent metrics.
const hosts=new Map(),listeners=new Map();
const keyFor=(host,thread)=>JSON.stringify([host,thread]);
const validCount=n=>Number.isFinite(n)&&n>=0;
const toolTypes=new Set(['commandExecution','fileChange','mcpToolCall','dynamicToolCall','webSearch','imageGeneration','collabAgentToolCall']);
const events=new Set(['turn/started','turn/completed','thread/tokenUsage/updated','thread/deleted','item/started','item/completed']);
function emit(host,thread){for(const callback of listeners.get(keyFor(host,thread))??[])callback();}
export function subscribeSpeed(host,thread,callback){
  const key=keyFor(host,thread),callbacks=listeners.get(key)??new Set();
  callbacks.add(callback);listeners.set(key,callbacks);
  return()=>{callbacks.delete(callback);if(!callbacks.size)listeners.delete(key);};
}
export function readSpeed(host,thread){return hosts.get(host)?.get(thread)?.speed??null;}
function resetSegment(state,now){state.started=now;state.paused=0;state.blockedAt=state.tools.size?now:null;}
function elapsed(state,now){return state.started==null?null:Math.max(0,now-state.started-state.paused-(state.blockedAt==null?0:now-state.blockedAt))/1000;}
function publish(host,thread,state){
  const seconds=state.samples.reduce((sum,sample)=>sum+sample.seconds,0);
  const output=state.samples.reduce((sum,sample)=>sum+sample.output,0);
  const rate=seconds>0?output/seconds:null;
  const next=rate!=null&&rate>0&&rate<1e6?Math.round(rate):null;
  if(next!==state.speed){state.speed=next;emit(host,thread);}
}
export function observeMetric(host,method,params,now=performance.now()){
  if(method==='account/updated'||method==='account/login/completed'){
    const threads=hosts.get(host);hosts.delete(host);
    for(const thread of threads?.keys()??[])emit(host,thread);
    return;
  }
  const thread=params?.threadId;
  if(typeof host!=='string'||typeof thread!=='string'||!events.has(method)||!Number.isFinite(now))return;
  let threads=hosts.get(host);if(!threads){threads=new Map();hosts.set(host,threads);}
  if(method==='thread/deleted'){threads.delete(thread);emit(host,thread);return;}
  let state=threads.get(thread);
  if(!state){state={total:null,turn:null,active:false,started:null,paused:0,blockedAt:null,tools:new Set(),samples:[],speed:null};threads.set(thread,state);if(threads.size>256)threads.delete(threads.keys().next().value);}
  if(method==='turn/started'){
    const turn=params.turn?.id;if(typeof turn!=='string'||turn===state.turn)return;
    state.turn=turn;state.active=true;state.tools.clear();resetSegment(state,now);return;
  }
  if(method==='turn/completed'){
    if(params.turn?.id!==state.turn)return;
    state.active=false;state.tools.clear();state.started=null;state.blockedAt=null;return;
  }
  if(method==='item/started'||method==='item/completed'){
    const item=params.item;
    if(!state.active||params.turnId!==state.turn||!toolTypes.has(item?.type)||typeof item.id!=='string')return;
    if(method==='item/started'){
      if(!state.tools.size)state.blockedAt=now;
      state.tools.add(item.id);
    }else if(state.tools.delete(item.id)&&!state.tools.size){
      state.paused+=Math.max(0,now-state.blockedAt);state.blockedAt=null;
    }
    return;
  }
  const total=params.tokenUsage?.total?.outputTokens,last=params.tokenUsage?.last?.outputTokens;
  if(!validCount(total)||total===state.total)return;
  if(state.total!=null&&total<state.total){
    state.total=total;state.samples=[];resetSegment(state,state.active?now:null);publish(host,thread,state);return;
  }
  state.total=total;
  const seconds=elapsed(state,now);
  // Include prefill/first-token waiting, unlike the former first/last-delta timer.
  // Tool intervals are excluded as a union, so parallel tools aren't subtracted twice.
  // A mid-response attach has no known start and cannot fabricate throughput.
  if(state.active&&!state.tools.size&&validCount(last)&&last>0&&seconds>=.25){
    state.samples.push({output:last,seconds});state.samples=state.samples.slice(-10);
  }
  resetSegment(state,state.active?now:null);publish(host,thread,state);
}
