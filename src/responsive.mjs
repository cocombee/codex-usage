// Fit the actual content, including the native diff control and current font.
// Each stage is tried before any metric could be moved onto another row.
const stageFor = level => level === 0 ? 0 : level <= 2 ? 1 : level <= 5 ? 2 : 3;

export function fitBar(bar) {
  const previous = Number(bar.dataset.cuFit || 0);
  const style = getComputedStyle(bar);
  const chatWidth = parseFloat(style.width) + (parseFloat(style.getPropertyValue('--cu-chat-extra')) || 0);
  let minimumStage = chatWidth <= 490 ? 3 : chatWidth <= 580 ? 2 : chatWidth <= 620 ? 1 : 0;
  const previousStage = stageFor(previous);
  const boundary = [Infinity,620,580,490][previousStage];
  if (minimumStage < previousStage && chatWidth <= boundary + 8) minimumStage = previousStage;
  const firstLevel = [0,2,3,6][minimumStage];
  const setSize = (name,value) => {
    if (bar.style.getPropertyValue(name) !== value) bar.style.setProperty(name,value);
  };
  for (let level = firstLevel; level <= 8; level++) {
    bar.dataset.cuFit = String(level);
    bar.dataset.cuStage = String(stageFor(level));
    setSize('--cu-track-base',level === 0 ? '100px' : '16px');
    // Measure natural widths without flex growth or the previous track extension.
    bar.dataset.cuMeasure = '';
    const style = getComputedStyle(bar), logicalWidth = parseFloat(style.width);
    const scale = bar.currentCSSZoom > 0 ? bar.currentCSSZoom : logicalWidth > 0 ? bar.getBoundingClientRect().width / logicalWidth : 1;
    const widths = [...bar.children].map(el=>el.getBoundingClientRect().width / (scale || 1)).filter(width=>width>0);
    const natural = widths.reduce((sum,width)=>sum+width,0) + (parseFloat(style.columnGap)||0) * Math.max(0,widths.length-1);
    const spare = logicalWidth - natural;
    delete bar.dataset.cuMeasure;
    if (spare < -.1 && level < 8) continue;
    // Restore a fuller stage only with 8 logical pixels of breathing room.
    if (level < previous && spare < 8) continue;
    const extra = Math.max(0,spare)*0.70;
    setSize('--cu-track-extra',`${extra}px`);
    const bounds = bar.getBoundingClientRect();
    const pills = [...bar.children].map(el=>el.getBoundingClientRect()).filter(rect=>rect.width>0);
    const fits = pills.every(rect=>rect.left>=bounds.left-.25 && rect.right<=bounds.right+.25) && bar.scrollWidth<=bar.clientWidth;
    if (fits || level === 8) {
      if (fits) bar.parentElement.removeAttribute('tabindex');
      else bar.parentElement.tabIndex = 0;
      return level;
    }
  }
}

export function useBarFit(React, barRef) {
  React.useLayoutEffect(() => {
    const bar = barRef.current;
    if (!bar) return;
    let frame = null;
    const schedule = () => {
      if (frame == null) frame = requestAnimationFrame(() => {
        frame = null;
        fitBar(bar);
      });
    };
    const resize = new ResizeObserver(schedule);
    resize.observe(bar);
    resize.observe(bar.parentElement);
    // These objects keep their intrinsic widths while the pills absorb spare
    // space. Their sizes also change when an inherited font/style changes or a
    // selected font finishes loading, even if the bar's own box stays fixed.
    const objects = new Set();
    const observeObjects = () => {
      const current = new Set(bar.querySelectorAll('.cu-pill > :not(.cu-track), .cu-changes button'));
      for (const object of objects) if (!current.has(object)) {
        resize.unobserve(object); objects.delete(object);
      }
      for (const object of current) if (!objects.has(object)) {
        resize.observe(object); objects.add(object);
      }
    };
    observeObjects();
    // The fitter owns the bar's style variable; observing its own writes would
    // requeue fitting. Metric/native-control styles and content still trigger it.
    const mutations = new MutationObserver(records=>{
      if (records.some(record=>record.type==='childList')) observeObjects();
      if (records.some(record=>record.target!==bar || record.attributeName!=='style')) schedule();
    });
    mutations.observe(bar, {subtree:true, childList:true, characterData:true,
      attributes:true, attributeFilter:['class','style']});
    fitBar(bar);
    return () => {
      resize.disconnect(); mutations.disconnect();
      if (frame != null) cancelAnimationFrame(frame);
    };
  }, [barRef]);
}
