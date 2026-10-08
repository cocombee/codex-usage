import {useDiffSlot} from './diff-slot.mjs';

// Dependencies are the version-pinned host's existing components and selectors.
// Reuse its diff button; keep plans and additional native portals above the bar.
export function renderNativeFixed(props, host) {
  const {conversationId,hasBlockingRequest,isTurnInProgress,todoListItem,
    unifiedDiffItem,conversationDetailLevel,cwd,hostId}=props;
  const {React,jsx,DOM,anchor,useSelector,diffAtom,cwdAtom,extraAtom,summarize,
    Diff,Motion,Presence,Todo,Layout,fade,layout,delay}=host;
  const target=useDiffSlot(React,hostId,conversationId);
  const container=anchor(conversationId);
  const setup=anchor(conversationId,'[data-environment-setup-progress-content]');
  const latestDiff=useSelector(diffAtom,conversationId);
  const latestCwd=useSelector(cwdAtom,conversationId);
  const extra=useSelector(extraAtom,conversationId);
  if(!container || !isTurnInProgress) return null;
  const item=(latestDiff==null?null:{type:'turn-diff',unifiedDiff:latestDiff,cwd:latestCwd??null})??unifiedDiffItem;
  const summary=!hasBlockingRequest&&unifiedDiffItem!=null&&item!=null&&conversationDetailLevel!=='STEPS_PROSE'
    ?summarize(item.unifiedDiff):null;
  const hasDiff=summary?.hasChanges===true;
  const hasPlan=!hasBlockingRequest&&todoListItem!=null&&todoListItem.plan.length>0;
  if(!hasDiff&&!hasPlan&&extra==null) return null;
  const diff=hasDiff&&item!=null?jsx.jsx(Diff,{
    isInProgress:true,inProgressDiffSummary:summary,item,showLeadingSeparator:!target&&hasPlan,
    conversationId,cwd:item.cwd??cwd,hostId},'diff'):null;
  const marker={'data-cu-existing-row':true};
  const rows=jsx.jsxs(Presence,{initial:false,children:[
    extra==null?null:jsx.jsx('div',{...marker,style:{display:'contents'},children:jsx.jsx(extra.Summary,{conversationId})},'extra'),
    !hasPlan?null:jsx.jsx(Motion.div,{...marker,className:'max-w-full min-w-0 shrink-0',
      initial:{opacity:0},animate:{opacity:1},exit:{opacity:0},transition:fade,
      children:jsx.jsx(Todo,{donutAnimateOnMountDelayMs:delay*1000,item:todoListItem,tooltipPortalContainer:container})},'todo'),
    !diff||target?null:jsx.jsx(Motion.div,{...marker,className:hasPlan?'min-w-0':'min-w-0 shrink-0',
      initial:{opacity:0},animate:{opacity:1},exit:{opacity:0},transition:fade,children:diff},'diff'),
    jsx.jsx('div',{className:'flex min-w-0 items-center gap-2 empty:hidden',
      'data-cu-extra':true,'data-above-composer-portal':true,
      'data-above-composer-conversation-id':conversationId,'data-above-composer-fixed-content-portal':true},'additional-fixed-content')
  ]});
  const upper=setup!=null?rows:jsx.jsx('div',{
    className:'relative col-start-1 row-start-1 h-8 self-end',
    'data-in-progress-fixed-content':true,'data-cu-above-panel':true,
    children:jsx.jsx(Presence,{children:jsx.jsx(Motion.div,{
      className:'absolute inset-x-0 bottom-1 flex min-h-7 items-center justify-center gap-2 pb-1',
      initial:{opacity:0,y:4},animate:{opacity:1,y:0},exit:{opacity:0,y:4},transition:fade,
      children:jsx.jsx(Layout,{transition:layout,children:rows})},'fixed-content')})});
  return jsx.jsxs(jsx.Fragment,{children:[
    diff&&target?DOM.createPortal(diff,target,'codex-usage-diff'):null,
    DOM.createPortal(upper,setup??container,'codex-usage-native-panels')
  ]});
}
