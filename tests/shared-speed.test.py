"""Both adapters deliver the same speed lifecycle; no real app is read or built."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import mod
import windows_patch


class RendererFixture:
    def __init__(self, adapter):
        if adapter is mod:
            primary = '\n'.join([
                'Oe=(0,UR.jsxs)(pR.Item,{children:[se,De]})',
                'className:Lr(`flex w-full flex-col gap-2`,Ne&&`relative`),onPaste:Ri?Dl:void 0',
                '(0,gZ.jsx)(zt,{initial:!1,children:Jl&&c==null?',
            ])
            turn = 'function Ho(e){return e}var Uo,Wo,Go,Ko,qo,Jo;'
            initial = '(Rs.div,{"aria-hidden":u,className:f,inert:p,initial:m,animate:h,exit:g,transition:_,children:b})'
        else:
            primary = '\n'.join([
                'Oe=(0,jR.jsxs)(QL.Item,{children:[ce,De]})',
                'className:ld(`flex w-full flex-col gap-2`,Ue&&`relative`),onPaste:Yi?Ul:void 0',
                '(0,WX.jsx)(ae,{initial:!1,children:lu&&s==null?',
            ])
            turn = 'function Vo(e){return e}var Ho,Uo,Wo,Go,Ko,qo;'
            initial = '(gc.div,{"aria-hidden":u,className:f,inert:p,initial:m,animate:h,exit:g,transition:_,children:b})'
        self.files = {
            adapter.PRIMARY: primary,
            adapter.SHARED: 'onNotification(e,t,n=null,r,i=Date.now()){',
            adapter.TURN: turn,
            adapter.INITIAL: initial,
        }

    def read(self, path):
        return self.files[path].encode('utf-8')


class SharedSpeedTests(unittest.TestCase):
    def test_packaged_speed_clears_on_completion_for_both_adapters(self):
        # Both adapters read text and normalize a Windows checkout's CRLF.
        expected = (mod.ROOT / 'src/speed.mjs').read_text(encoding='utf-8').encode('utf-8')
        for adapter in (mod, windows_patch):
            with self.subTest(adapter=adapter.__name__):
                modules = adapter.patch_sources(RendererFixture(adapter))
                speed = modules['webview/assets/codex-usage-speed.mjs']
                self.assertEqual(speed, expected)
                self.assertIn(b'__cuObserve(this.hostId,e,t)', modules[adapter.SHARED])
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / 'speed.mjs').write_bytes(speed)
                    (root / 'check.mjs').write_text('''
import assert from 'node:assert/strict';
import {observeMetric, readSpeed, subscribeSpeed} from './speed.mjs';
const notices = [];
subscribeSpeed('host', 'chat', () => notices.push(readSpeed('host', 'chat')));
observeMetric('host', 'turn/started', {threadId:'chat', turn:{id:'turn'}}, 0);
observeMetric('host', 'thread/tokenUsage/updated', {
  threadId:'chat', tokenUsage:{last:{outputTokens:110},total:{outputTokens:110}}
}, 5000);
assert.equal(readSpeed('host', 'chat'), 22);
observeMetric('host', 'turn/completed', {threadId:'chat',turn:{id:'turn'}}, 5100);
assert.equal(readSpeed('host', 'chat'), null);
assert.deepEqual(notices, [22, null]);
''', encoding='utf-8')
                    subprocess.run(['node', str(root / 'check.mjs')], check=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
