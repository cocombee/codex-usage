import test from 'node:test';
import assert from 'node:assert/strict';
import {weeklyWindow, contextPercent, percentText, resetText, remainingPercent} from '../src/metrics.mjs';

test('weekly selection is by duration, including swapped primary/secondary slots', () => {
  const week = {windowDurationMins:10080, usedPercent:0, resetsAt:1800000000};
  assert.equal(weeklyWindow([{snapshot:{primary:week, secondary:{windowDurationMins:300,usedPercent:50}}}]), week);
  assert.equal(weeklyWindow([{snapshot:{primary:{windowDurationMins:300},secondary:week}}]), week);
  assert.equal(weeklyWindow([{snapshot:{secondary:{windowDurationMins:10080,usedPercent:null}}}]), null);
});

test('Context uses the current last snapshot, never lifetime totals', () => {
  assert.equal(percentText(contextPercent({modelContextWindow:1000,last:{totalTokens:290},total:{totalTokens:100000}})), '29%');
  assert.equal(contextPercent({modelContextWindow:1000,last:{totalTokens:0}}), 0);
  assert.equal(contextPercent({modelContextWindow:0,last:{totalTokens:5}}), null);
  assert.equal(contextPercent({modelContextWindow:1000,last:{}}), null);
});

test('missing values stay unknown, expiry cannot invent a reset', () => {
  assert.equal(percentText(null), '—'); assert.equal(percentText(0), '0%');
  assert.equal(resetText(null, 0), '—');
  assert.equal(resetText(13*3600,0,true),'13h');assert.equal(resetText(59*60,0,true),'59m');
  assert.equal(resetText(13*3600,0),'13h');assert.equal(resetText(13*3600+30*60,0),'13h');
  assert.equal(resetText(100, 100001), 'Updating');
  assert.equal(resetText(5*86400+9*3600,0,true),'5d');
  assert.equal(resetText(100 + 5 * 86400 + 9 * 3600, 100000), '5d 9h');
});

test('remaining quota warning boundaries are inclusive at 20% and 10%',async()=>{
  const {quotaTone}=await import('../src/metrics.mjs');
  for(const [used,tone] of [[0,'normal'],[79.99,'normal'],[80,'warning'],[80.01,'warning'],[89.99,'warning'],[90,'low'],[90.01,'low']]) assert.equal(quotaTone(used),tone);
  assert.equal(quotaTone(100),'low');assert.equal(quotaTone(105),'low');
  assert.equal(quotaTone(null),'normal');assert.equal(quotaTone(NaN),'normal');
});

test('weekly remaining quota matches Codex: 8% used is 92% left',()=>{
  assert.equal(remainingPercent(8),92);assert.equal(remainingPercent(0),100);
  assert.equal(remainingPercent(100),0);assert.equal(remainingPercent(null),null);
});
