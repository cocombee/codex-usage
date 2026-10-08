import test from 'node:test';
import assert from 'node:assert/strict';
import {setDiffSlot,readDiffSlot,subscribeDiffSlot} from '../src/diff-slot.mjs';

test('portal ownership is isolated by host and chat and cleaned on unmount',()=>{
  const first={},replacement={},second={};let notifications=0;
  const stop=subscribeDiffSlot('a','chat',()=>notifications++);
  setDiffSlot('a','chat',first);setDiffSlot('a','chat',first);
  setDiffSlot('b','chat',second);
  assert.equal(notifications,1);assert.equal(readDiffSlot('a','chat'),first);
  assert.equal(readDiffSlot('b','chat'),second);assert.equal(readDiffSlot('a','other'),null);
  setDiffSlot('a','chat',replacement);assert.equal(notifications,2);
  setDiffSlot('a','chat',null);assert.equal(readDiffSlot('a','chat'),null);assert.equal(notifications,3);
  stop();setDiffSlot('a','chat',first);assert.equal(notifications,3);
  setDiffSlot('a','chat',null);setDiffSlot('b','chat',null);
});
