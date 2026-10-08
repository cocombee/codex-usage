import test from 'node:test';
import assert from 'node:assert/strict';
import {observeMetric,readSpeed,subscribeSpeed} from '../src/speed.mjs';
const emit=(host,thread,method,params,now)=>observeMetric(host,method,{threadId:thread,...params},now);
function sample(host,thread,turn,output,total,start,seconds,complete=true){
  emit(host,thread,'turn/started',{turn:{id:turn}},start);
  emit(host,thread,'thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:output},total:{outputTokens:total}}},start+seconds*1000);
  if(complete)emit(host,thread,'turn/completed',{turn:{id:turn}},start+seconds*1000+10);
}
const tool=(host,method,id,now)=>emit(host,'thread',method,{turnId:'a',item:{id,type:'commandExecution'}},now);

test('weighted throughput uses full elapsed waits, matching the Hermes aggregate formula',()=>{
  sample('weighted','thread','a',130,130,1000,2.1);sample('weighted','thread','b',190,320,100000,4.3,false);
  assert.equal(readSpeed('weighted','thread'),50);
  emit('weighted','thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:190},total:{outputTokens:320}}},110000);
  assert.equal(readSpeed('weighted','thread'),50);
});
test('prefill and first-token wait are included: 109 tokens in 5 seconds is 22, not 109',()=>{
  emit('prefill','thread','turn/started',{turn:{id:'a'}},0);
  emit('prefill','thread','item/agentMessage/delta',{turnId:'a',delta:'x'},4000);
  emit('prefill','thread','item/agentMessage/delta',{turnId:'a',delta:'x'},5000);
  emit('prefill','thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:109},total:{outputTokens:109}}},5000);
  assert.equal(readSpeed('prefill','thread'),22);
});
test('parallel tool intervals are subtracted once and old-turn tools ignored',()=>{
  emit('tools','thread','turn/started',{turn:{id:'a'}},0);
  tool('tools','item/started','one',1000);tool('tools','item/started','two',2000);
  tool('tools','item/completed','one',5000);tool('tools','item/completed','two',6000);
  emit('tools','thread','item/started',{turnId:'old',item:{id:'wrong',type:'commandExecution'}},7000);
  emit('tools','thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:110},total:{outputTokens:110}}},10000);
  assert.equal(readSpeed('tools','thread'),22);
});
test('mid-turn attach, late usage, and overlapping tool usage never invent speed',()=>{
  emit('missing','thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:100},total:{outputTokens:100}}},3000);
  assert.equal(readSpeed('missing','thread'),null);
  emit('missing','thread','turn/started',{turn:{id:'a'}},4000);
  tool('missing','item/started','one',4500);
  emit('missing','thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:200},total:{outputTokens:300}}},6000);
  assert.equal(readSpeed('missing','thread'),null);
  emit('missing','thread','turn/completed',{turn:{id:'a'}},6500);
  emit('missing','thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:100},total:{outputTokens:400}}},7000);
  assert.equal(readSpeed('missing','thread'),null);
});
test('host/chat isolation, account clearing, subscriptions and ten-response limit',()=>{
  sample('host-a','same','a',100,100,0,1,false);sample('host-b','same','a',300,300,0,1,false);
  assert.equal(readSpeed('host-a','same'),100);assert.equal(readSpeed('host-b','same'),300);
  let calls=0;const stop=subscribeSpeed('host-a','same',()=>calls++);observeMetric('host-a','account/updated',{},2000);
  assert.equal(readSpeed('host-a','same'),null);assert.equal(calls,1);assert.equal(readSpeed('host-b','same'),300);stop();
  for(let n=0;n<11;n++)sample('ten','thread',String(n),n===0?1000:10,1000+n*10,n*10000,1,n<10);
  assert.equal(readSpeed('ten','thread'),10);
});
test('counter reset clears incomparable samples',()=>{
  sample('reset','thread','a',100,2000,0,1,false);
  emit('reset','thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:10},total:{outputTokens:10}}},2000);
  assert.equal(readSpeed('reset','thread'),null);
});

for(const status of ['completed','failed','interrupted'])test(`${status} turns clear speed immediately and late usage cannot revive it`,()=>{
  const host=`terminal-${status}`;
  sample(host,'thread','a',100,100,0,1,false);
  const values=[],stop=subscribeSpeed(host,'thread',()=>values.push(readSpeed(host,'thread')));
  emit(host,'thread','turn/completed',{turn:{id:'a',status}},1100);
  assert.equal(readSpeed(host,'thread'),null);
  assert.deepEqual(values,[null]);
  emit(host,'thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:50},total:{outputTokens:150}}},2000);
  emit(host,'thread','turn/completed',{turn:{id:'a',status}},2100);
  assert.equal(readSpeed(host,'thread'),null);
  assert.deepEqual(values,[null]);
  stop();
});

test('a new turn waits for a fresh valid sample while retaining weighted history',()=>{
  const host='fresh-turn';
  sample(host,'thread','a',100,100,0,1);
  emit(host,'thread','turn/started',{turn:{id:'b'}},2000);
  assert.equal(readSpeed(host,'thread'),null);
  emit(host,'thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:100},total:{outputTokens:100}}},2500);
  assert.equal(readSpeed(host,'thread'),null);
  emit(host,'thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:0},total:{outputTokens:150}}},3000);
  assert.equal(readSpeed(host,'thread'),null);
  emit(host,'thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:100},total:{outputTokens:250}}},5000);
  assert.equal(readSpeed(host,'thread'),67);
});

test('a distinct turn clears stale speed without completion and ignores older completions',()=>{
  const host='replaced-turn';
  sample(host,'thread','a',100,100,0,1,false);
  const values=[],stop=subscribeSpeed(host,'thread',()=>values.push(readSpeed(host,'thread')));
  emit(host,'thread','turn/started',{turn:{id:'b'}},2000);
  assert.equal(readSpeed(host,'thread'),null);
  emit(host,'thread','turn/completed',{turn:{id:'a'}},2100);
  emit(host,'thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:50},total:{outputTokens:150}}},2200);
  assert.equal(readSpeed(host,'thread'),null);
  emit(host,'thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:200},total:{outputTokens:350}}},3200);
  assert.equal(readSpeed(host,'thread'),150);
  emit(host,'thread','turn/completed',{turn:{id:'a'}},3300);
  emit(host,'thread','turn/started',{turn:{id:'b'}},3400);
  assert.equal(readSpeed(host,'thread'),150);
  emit(host,'thread','turn/completed',{turn:{id:'b'}},3500);
  assert.deepEqual(values,[null,150,null]);
  stop();
});

test('completion clears only its host and conversation',()=>{
  sample('isolation','first','a',100,100,0,1,false);
  sample('isolation','second','a',200,200,0,1,false);
  sample('another-host','first','a',300,300,0,1,false);
  emit('isolation','first','turn/completed',{turn:{id:'a'}},1100);
  assert.equal(readSpeed('isolation','first'),null);
  assert.equal(readSpeed('isolation','second'),200);
  assert.equal(readSpeed('another-host','first'),300);
});

test('idle thread status clears speed but active status cannot invent turn timing',()=>{
  const host='runtime-status';
  sample(host,'thread','a',100,100,0,1,false);
  const values=[],stop=subscribeSpeed(host,'thread',()=>values.push(readSpeed(host,'thread')));
  emit(host,'thread','thread/status/changed',{status:{type:'active'}},1050);
  assert.equal(readSpeed(host,'thread'),100);
  emit(host,'thread','thread/status/changed',{status:{type:'idle'}},1100);
  assert.equal(readSpeed(host,'thread'),null);
  assert.deepEqual(values,[null]);
  emit(host,'thread','thread/status/changed',{status:{type:'active'}},2000);
  emit(host,'thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:100},total:{outputTokens:200}}},3000);
  assert.equal(readSpeed(host,'thread'),null);
  assert.deepEqual(values,[null]);
  emit(host,'thread','turn/started',{turn:{id:'b'}},4000);
  emit(host,'thread','thread/tokenUsage/updated',{tokenUsage:{last:{outputTokens:100},total:{outputTokens:300}}},5000);
  assert.equal(readSpeed(host,'thread'),100);
  assert.deepEqual(values,[null,100]);
  stop();
});
