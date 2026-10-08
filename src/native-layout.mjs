import {fitBar} from './responsive.mjs';

function zoomOf(element) {
  // CSSOM View currentCSSZoom reports cumulative effective CSS zoom.
  // https://drafts.csswg.org/cssom-view/#dom-element-currentcsszoom
  if (element.currentCSSZoom > 0) return element.currentCSSZoom;
  const logical = parseFloat(getComputedStyle(element).width) || element.offsetWidth;
  return logical > 0 ? element.getBoundingClientRect().width / logical : 1;
}

// Native bars keep their positioning and geometry. Reserve their measured
// overflow in the composer stack so the preceding Usage row cannot overlap.
export function useNativeLayout(React, placementRef) {
  React.useLayoutEffect(() => {
    const placement = placementRef.current;
    const scope = placement?.parentElement;
    if (!scope) return;
    // Resolve the native Goal rail's CSS inset without changing native nodes.
    const insetProbe = document.createElement('span');
    insetProbe.setAttribute('aria-hidden','true');
    insetProbe.style.cssText = 'position:absolute;visibility:hidden;pointer-events:none;height:0;width:var(--home-composer-inline-inset,0px)';
    placement.append(insetProbe);
    const originals = new Map();
    let frame;
    const resize = new ResizeObserver(() => schedule());
    function update() {
      frame = null;
      const stack = scope.querySelector('[data-cu-composer-stack]');
      if (!stack) return;
      if (!originals.has(stack)) originals.set(stack, {
        inline: stack.style.paddingTop,
        pixels: parseFloat(getComputedStyle(stack).paddingTop) || 0,
      });
      const original = originals.get(stack);
      const visible = element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 &&
          !element.closest('[aria-hidden="true"],[inert]') &&
          getComputedStyle(element).visibility !== 'hidden';
      };
      const utility = [...scope.querySelectorAll('[data-cu-native-utility]')].find(visible);
      const railIn = parent => {
        if (!parent) return null;
        for (const selector of ['[data-composer-rail][data-composer-rail-placement="above"]',
          '[data-composer-rail-framed="true"][data-composer-rail-placement="above"]']) {
          const candidates = parent.matches(selector) ? [parent, ...parent.querySelectorAll(selector)] :
            [...parent.querySelectorAll(selector)];
          const match = candidates.find(visible);
          if (match) return match;
        }
        return null;
      };
      // Goal is the primary width reference. Avoid arbitrary inner items and
      // empty/exiting rails; when Goal is absent, retain its native inset.
      const goal = [...scope.querySelectorAll('[data-cu-native-goal]')].find(visible);
      const goalRail = goal?.closest('[data-composer-rail]') ?? goal?.closest('[data-composer-rail-framed="true"]');
      // Utility wrappers are the complete native frame. Do not use a narrower
      // framed/contained item inside them as the outer width reference.
      const rail = (goalRail && visible(goalRail) ? goalRail : null) ?? utility ?? railIn(scope);
      const surface = [...stack.querySelectorAll('[data-composer-surface-variant]')].find(visible);
      if (surface) resize.observe(surface);
      const target = rail ?? surface;
      if (target) {
        resize.observe(target);
        const rect = target.getBoundingClientRect();
        const scale = zoomOf(placement);
        const inset = rail ? 0 : parseFloat(getComputedStyle(insetProbe).width) || 0;
        const width = `${Math.max(0,rect.width / scale - 2 * inset)}px`;
        if (placement.style.width !== width) placement.style.width = width;
        // Native composer surfaces can extend beyond their layout parent.
        // Centering in that parent is insufficient; follow the painted edge.
        if (placement.style.marginRight !== '0px') placement.style.marginRight = '0px';
        const own = placement.getBoundingClientRect();
        const left = rect.left + inset * scale;
        const delta = left - own.left;
        if (Math.abs(delta) > .25) {
          const current = parseFloat(getComputedStyle(placement).marginLeft) || 0;
          placement.style.marginLeft = `${current + delta / scale}px`;
        }
      } else {
        for (const property of ['width','marginLeft','marginRight']) {
          if (placement.style[property]) placement.style[property] = '';
        }
      }
      let reserve = 0;
      for (const nativeUtility of stack.querySelectorAll('[data-cu-native-utility]')) {
        resize.observe(nativeUtility);
        const style = getComputedStyle(nativeUtility);
        if (style.position === 'absolute' && style.bottom !== 'auto' && style.display !== 'none') {
          const extras = style.boxSizing === 'border-box' ? 0 :
            ['paddingTop','paddingBottom','borderTopWidth','borderBottomWidth'].reduce((sum,key)=>sum+(parseFloat(style[key])||0),0);
          reserve = Math.max(reserve, (parseFloat(style.height)||0) + extras);
        }
      }
      const wanted = `${original.pixels + reserve}px`;
      if (stack.style.paddingTop !== wanted) stack.style.paddingTop = wanted;
      const parent = getComputedStyle(scope);
      const margin = parent.display.includes('flex') && parent.flexDirection === 'column' && parseFloat(parent.rowGap) >= 8 ? '0px' : '8px';
      if (placement.style.marginBottom !== margin) placement.style.marginBottom = margin;
      const bar = placement.querySelector('.cu-bar');
      if (bar) {
        const logical = parseFloat(getComputedStyle(placement).width) || placement.offsetWidth;
        const scale = zoomOf(placement);
        const extra = surface ? Math.max(0,surface.getBoundingClientRect().width / (scale || 1)-logical) : 0;
        const value = `${extra}px`;
        if (bar.style.getPropertyValue('--cu-chat-extra') !== value) bar.style.setProperty('--cu-chat-extra',value);
        fitBar(bar);
      }
    }
    function schedule() {
      if (frame == null) frame = requestAnimationFrame(update);
    }
    const mutations = new MutationObserver(records=>{
      // Responsive fitting owns the bar's CSS variables. Its temporary
      // measurements must not enqueue another native-layout frame.
      if (records.some(record=>record.attributeName!=='style' || !record.target.matches?.('.cu-bar'))) schedule();
    });
    mutations.observe(scope, {childList:true, subtree:true, attributes:true, attributeFilter:['class','style','aria-hidden']});
    resize.observe(placement);
    update();
    return () => {
      mutations.disconnect(); resize.disconnect();
      insetProbe.remove();
      if (frame != null) cancelAnimationFrame(frame);
      for (const [stack, original] of originals) stack.style.paddingTop = original.inline;
    };
  }, [placementRef]);
}
