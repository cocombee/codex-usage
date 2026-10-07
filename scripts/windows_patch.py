"""Inspected Windows renderer adapter for Store package 26.1002.7124.0 (x64)."""
from mod import ROOT, unique_replace

VERSION = '26.1002.7124.0'
APP_VERSION = '26.1002.52244'
PINNED = {
    'resources/app.asar': '76fe7078248c00e4e03dd2177a4275ec9ce158a9dd43452a4f0427d39a4ed012',
    'ChatGPT.exe': '2b4898ac0915072107aac1bdd91e8784ca48a2ef9ead7a5c349c3f06cd9e6ee4',
    'chrome.dll': '80cbec95e543836564ea8c951b6ffafa9a7bc6cb54a32d094328b5f163291ac3',
}
PRIMARY = 'webview/assets/app-primary-2b28b2369958.js'
SHARED = 'webview/assets/app-shared-40678a67f0e3.js'
TURN = 'webview/assets/local-conversation-turn-133c4f6f07f4.js'
INITIAL = 'webview/assets/app-initial-25361a10f2bf.js'
ASSETS = (PRIMARY, SHARED, TURN, INITIAL)


def patch_sources(archive):
    primary, shared, turn, initial = (archive.read(path).decode('utf-8') for path in ASSETS)
    primary = unique_replace(primary, 'Oe=(0,jR.jsxs)(QL.Item,{children:[ce,De]})',
                            'Oe=(0,jR.jsxs)(QL.Item,{"data-cu-native-goal":true,children:[ce,De]})', 'Windows Goal marker')
    anchor = 'onNotification(e,t,n=null,r,i=Date.now()){'
    shared = unique_replace(shared, anchor, anchor + 'try{__cuObserve(this.hostId,e,t)}catch{}', 'Windows notification observer')
    shared = 'import{observeMetric as __cuObserve}from"./codex-usage-speed.mjs";\n' + shared
    anchor = 'className:ld(`flex w-full flex-col gap-2`,Ue&&`relative`),onPaste:Yi?Ul:void 0'
    primary = unique_replace(primary, anchor, '"data-cu-composer-stack":true,' + anchor, 'Windows composer stack')
    anchor = '(0,WX.jsx)(ae,{initial:!1,children:lu&&s==null?'
    primary = unique_replace(primary, anchor,
        'Ut!==`cloud`?(0,WX.jsx)(__cuHost,{conversationId:at,hostId:vt.hostId,rateLimit:ln}):null,' + anchor,
        'Windows usage placement')
    primary = ('import{useNativeLayout as __cuLayout}from"./codex-usage-native-layout.mjs";\n'
               'import{createBar as __cuCreateBar}from"./codex-usage-bar.mjs";\n' + primary + '''
let __cuBar;
function __cuHost({conversationId,hostId,rateLimit}){
  __cuBar??=__cuCreateBar(Pp(),Z());
  const placementRef=Pp().useRef(null);
  __cuLayout(Pp(),placementRef);
  const usage=$(kl,conversationId);
  const core=mSe(rateLimit).filter(entry=>entry.limitName==null);
  return Z().jsx(`div`,{ref:placementRef,"data-cu-placement":true,children:Z().jsx(__cuBar,{conversationId,hostId,usage,entries:core})});
}
''')
    start = turn.index('function Vo(e){')
    end = turn.index('var Ho,Uo,Wo,Go,Ko,qo;', start)
    turn = unique_replace(turn, turn[start:end], '''function Vo(e){
      return __cuFixed(e,{React:__cuLoadReact(),jsx:Wo,DOM:Uo,anchor:Pr,
        useSelector:J,diffAtom:cn,cwdAtom:xn,extraAtom:Rn,summarize:diff=>no(br(diff)),
        Diff:Aa,Motion:Te,Presence:u,Todo:pa,Layout:io,fade:Ko,layout:qo,delay:Go});
    }
    ''', 'Windows native fixed-content composition')
    turn = ('import{ggn as __cuLoadReact}from"./app-shared-40678a67f0e3.js";\n'
            'import{renderNativeFixed as __cuFixed}from"./codex-usage-native-fixed.mjs";\n' + turn)
    anchor = '(gc.div,{"aria-hidden":u,className:f,inert:p,initial:m,animate:h,exit:g,transition:_,children:b})'
    initial = unique_replace(initial, anchor, anchor.replace('{"aria-hidden":u', '{"data-cu-native-utility":true,"aria-hidden":u'), 'Windows utility marker')
    modules = {}
    for name in ['bar', 'metrics', 'speed', 'diff-slot', 'native-fixed', 'native-layout', 'responsive']:
        source = (ROOT / 'src' / (name + '.mjs')).read_text(encoding='utf-8')
        for dependency in ['metrics', 'speed', 'diff-slot', 'responsive']:
            source = source.replace("'./" + dependency + ".mjs'", "'./codex-usage-" + dependency + ".mjs'")
        modules['webview/assets/codex-usage-' + name + '.mjs'] = source.encode('utf-8')
    return {PRIMARY: primary.encode('utf-8'), SHARED: shared.encode('utf-8'),
            TURN: turn.encode('utf-8'), INITIAL: initial.encode('utf-8'), **modules}
