import {weeklyWindow, contextPercent, percentText, resetText, quotaTone, remainingPercent} from './metrics.mjs';
import {subscribeSpeed, readSpeed} from './speed.mjs';
import {useBarFit} from './responsive.mjs';
import {setDiffSlot} from './diff-slot.mjs';

export const styles = `
[data-cu-placement]{min-width:0;width:100%;margin-inline:auto}
.cu-shell{container-type:inline-size;width:100%;min-width:0;padding:0;box-sizing:border-box;font-size:var(--codex-chat-font-size,14px);overflow-x:auto;scrollbar-width:thin}
.cu-compact{display:none}
.cu-bar{display:flex;flex-wrap:nowrap;align-items:center;gap:8px;padding:0;border:0;border-radius:0;background:transparent;color:var(--color-text,#eee);font-family:inherit;font-size:inherit;font-weight:inherit;line-height:1.2;font-variant-numeric:tabular-nums;box-sizing:border-box;width:100%}
.cu-pill{display:flex;align-items:center;justify-content:space-evenly;gap:8px;background:var(--color-surface-elevated-secondary,#2a2a2a);border:1px solid color-mix(in oklab,var(--color-border,#444) 80%,transparent);border-radius:var(--radius-3xl,24px);padding:6px 8px;box-sizing:border-box;min-width:0;white-space:nowrap;flex:var(--cu-spaces,1) 0 auto}
.cu-week{--cu-spaces:5;min-width:min-content}.cu-speed{--cu-spaces:4}.cu-context{--cu-spaces:3}.cu-changes{--cu-spaces:2}
.cu-changes:empty{display:none}.cu-changes button,.cu-changes [class*="text-size-chat"]{font-size:inherit;line-height:inherit}
.cu-changes button{font-family:inherit;white-space:nowrap}
[data-cu-above-panel]:not(:has([data-cu-existing-row])):has([data-cu-extra]:empty){display:none}
.cu-label,.cu-reset,.cu-unit{color:var(--color-text-secondary,#aaa)}.cu-value{color:var(--color-text,#eee);font-weight:inherit}.cu-bolt{color:var(--color-text-secondary,#aaa)}
.cu-track{height:5.6px;width:calc(var(--cu-track-base,100px) + var(--cu-track-extra,0px));flex:0 0 calc(var(--cu-track-base,100px) + var(--cu-track-extra,0px));min-width:16px;background:color-mix(in srgb,var(--color-text,#eee) 10%,transparent);border-radius:99px;overflow:hidden}
.cu-bar[data-cu-measure] .cu-pill{flex-grow:0;flex-shrink:0}
.cu-bar[data-cu-measure] .cu-track{width:var(--cu-track-base,100px);flex-basis:var(--cu-track-base,100px)}
.cu-fill{height:100%;background:var(--color-background-primary-solid,var(--color-text,#eee));border-radius:inherit}.cu-unknown .cu-fill{width:0!important}
.cu-warning .cu-fill{background:var(--color-chart-yellow,var(--color-yellow,#e3b341))}
.cu-low .cu-fill{background:var(--color-chart-red,var(--color-red,#e54d4d))}
/* Three stages, with only the necessary reductions inside each stage. */
.cu-bar[data-cu-stage]:not([data-cu-stage="0"]){gap:5px}
.cu-bar[data-cu-stage]:not([data-cu-stage="0"]) .cu-pill{gap:6px;padding:6px}
.cu-bar:is([data-cu-fit="2"],[data-cu-fit="3"],[data-cu-fit="4"],[data-cu-fit="5"],[data-cu-fit="6"],[data-cu-fit="7"],[data-cu-fit="8"]) .cu-reset .cu-wide,
.cu-bar:is([data-cu-fit="2"],[data-cu-fit="3"],[data-cu-fit="4"],[data-cu-fit="5"],[data-cu-fit="6"],[data-cu-fit="7"],[data-cu-fit="8"]) .cu-left{display:none}
.cu-bar:is([data-cu-fit="2"],[data-cu-fit="3"],[data-cu-fit="4"],[data-cu-fit="5"],[data-cu-fit="6"],[data-cu-fit="7"],[data-cu-fit="8"]) .cu-reset .cu-compact{display:inline}
.cu-bar:is([data-cu-stage="2"],[data-cu-stage="3"]) .cu-wide{display:none}
.cu-bar:is([data-cu-stage="2"],[data-cu-stage="3"]) .cu-compact{display:inline}
.cu-bar:is([data-cu-fit="4"],[data-cu-fit="5"],[data-cu-fit="6"],[data-cu-fit="7"],[data-cu-fit="8"]) .cu-bolt{display:none}
.cu-bar:is([data-cu-fit="4"],[data-cu-fit="5"],[data-cu-fit="6"],[data-cu-fit="7"],[data-cu-fit="8"]) .cu-speed{--cu-spaces:3}
.cu-bar:is([data-cu-stage="2"],[data-cu-stage="3"]) .cu-week-label{display:none}
.cu-bar:is([data-cu-stage="2"],[data-cu-stage="3"]) .cu-week{--cu-spaces:4}
.cu-bar:is([data-cu-fit="5"],[data-cu-fit="6"]){gap:3px}
.cu-bar:is([data-cu-fit="5"],[data-cu-fit="6"]) .cu-pill{gap:3px;padding:6px 3px}
.cu-bar[data-cu-fit="6"]{font-size:min(var(--codex-chat-font-size,14px),14px)}
.cu-bar:is([data-cu-fit="7"],[data-cu-fit="8"]){font-size:min(var(--codex-chat-font-size,14px),12px);gap:3px}
.cu-bar:is([data-cu-fit="7"],[data-cu-fit="8"]) .cu-pill{gap:3px;padding:6px 3px}
.cu-bar[data-cu-fit="8"]{gap:2px}
.cu-bar[data-cu-fit="8"] .cu-pill{gap:2px;padding-inline:2px}
@media(forced-colors:active){.cu-pill{border:1px solid CanvasText}.cu-track{border:1px solid CanvasText}.cu-fill{background:Highlight}}
`;

// Host injects its existing React instance, avoiding duplicate React/state owners.
export function createBar(React, jsx) {
  return function CodexUsageBar({hostId, conversationId, entries, usage}) {
    const [, setTick] = React.useState(0);
    const barRef = React.useRef(null);
    useBarFit(React, barRef);
    const now = Date.now();
    React.useEffect(() => {
      const timer = setInterval(() => setTick(tick => tick + 1), 30000);
      return () => clearInterval(timer);
    }, []);
    const subscribe = React.useCallback(callback => subscribeSpeed(hostId, conversationId, callback), [hostId, conversationId]);
    const snapshot = React.useCallback(() => readSpeed(hostId, conversationId), [hostId, conversationId]);
    const speed = React.useSyncExternalStore(subscribe, snapshot, () => null);
    const diffRef = React.useCallback(node => setDiffSlot(hostId, conversationId, node), [hostId, conversationId]);
    const weekly = weeklyWindow(entries);
    const expired = weekly?.resetsAt != null && weekly.resetsAt * 1000 <= now;
    const context = contextPercent(usage);
    const remaining = expired ? null : remainingPercent(weekly?.usedPercent);
    const tone = quotaTone(weekly?.usedPercent);
    const h = (tag, props, ...children) => jsx.jsx(tag, {...props, children: children.length > 1 ? children : children[0]});
    return h('div', {className:'cu-shell', 'data-codex-usage':'0.1.0'},
      h('style', {}, styles),
      h('div', {className:'cu-bar', ref:barRef, role:'group', 'aria-label':'Codex Usage'},
        h('div', {className:`cu-pill cu-week${remaining == null ? ' cu-unknown' : ''}${tone==='normal'?'':` cu-${tone}`}`, title: weekly ? `Weekly quota: ${percentText(remainingPercent(weekly.usedPercent))} left; ${percentText(weekly.usedPercent)} used` : 'Weekly quota unavailable'},
          h('span', {className:'cu-label cu-week-label'}, 'Weekly'),
          h('span', {className:'cu-track', 'aria-hidden':true}, h('span', {className:'cu-fill', style:{display:'block', width:`${remaining ?? 0}%`}})),
          h('span', {className:'cu-value'}, percentText(remaining), remaining == null ? null : h('span', {className:'cu-wide cu-left'}, ' left')),
          h('span', {className:'cu-reset'},
            h('span', {className:'cu-wide'}, resetText(weekly?.resetsAt, now)),
            h('span', {className:'cu-compact'}, resetText(weekly?.resetsAt, now, true)))),
        h('div', {className:'cu-pill cu-changes', ref:diffRef}),
        h('div', {className:'cu-pill cu-speed', title: speed == null ? 'Token speed unavailable until an observed model response supplies token counts and elapsed timing' : 'Estimated throughput over up to 10 model responses: output tokens / elapsed model-wait seconds, including time before the first token and excluding observed tool execution. Codex does not expose provider API latency.'},
          h('span', {className:'cu-bolt', 'aria-hidden':true}, '⚡'),
          h('span', {className:'cu-value'}, speed == null ? '—' : `~${speed}`),
          h('span', {className:'cu-unit'}, h('span', {className:'cu-wide'}, 'token/s'), h('span', {className:'cu-compact'}, 'tok/s'))),
        h('div', {className:'cu-pill cu-context', title: context == null ? 'Context usage unavailable until Codex provides the current context size' : 'Current context window used'},
          h('span', {className:'cu-label'}, h('span', {className:'cu-wide'}, 'Context'), h('span', {className:'cu-compact'}, 'Ctx')), h('span', {className:'cu-value'}, percentText(context)))));
  };
}
