// Isolated fixture: exercises our actual composition adapter, using host React.
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import fs from 'node:fs/promises';
import path from 'node:path';
const runtime=process.env.CODEX_USAGE_NODE_MODULES;
if(!runtime)throw new Error('Set CODEX_USAGE_NODE_MODULES to the bundled runtime node_modules path');
const require=createRequire(import.meta.url),{chromium}=require(path.join(runtime,'playwright'));
const server=spawn('python3',['scripts/preview.py'],{stdio:['ignore','pipe','inherit']});let browser;
function check(value,message){if(!value)throw new Error(message);}
try{
  const [chunk]=await Promise.race([once(server.stdout,'data'),once(server,'exit').then(([code])=>{throw new Error('Fixture server exited: '+code);})]);
  browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const page=await browser.newPage(),errors=[],results=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(chunk.toString().trim());
  try{await page.waitForSelector('.cu-changes button',{timeout:5000});}catch(error){throw new Error(error.message+'; React errors: '+errors.join('; '));}
  async function measure(){return page.evaluate(()=>{
    const bar=document.querySelector('.cu-bar'),pills=[...bar.querySelectorAll('.cu-pill')].filter(p=>p.getBoundingClientRect().width>0);
    return{width:innerWidth,barWidth:bar.clientWidth,font:getComputedStyle(bar).fontSize,
      trackWidth:bar.querySelector('.cu-track').getBoundingClientRect().width,
      rows:new Set(pills.map(p=>Math.round(p.getBoundingClientRect().top))).size,
      values:pills.map(p=>p.innerText.replace(/\n/g,' ')),overflow:bar.scrollWidth>bar.clientWidth,
      clipped:pills.some(p=>p.scrollWidth>p.clientWidth),diffFont:bar.querySelector('button')?getComputedStyle(bar.querySelector('button')).fontSize:null,
      outerPadding:getComputedStyle(bar).padding,outerBackground:getComputedStyle(bar).backgroundColor,
      pillRadius:getComputedStyle(pills[0]).borderTopLeftRadius,
      fitStage:Number(bar.dataset.cuFit),stage:Number(bar.dataset.cuStage),shellOverflow:bar.parentElement.scrollWidth>bar.parentElement.clientWidth,pageOverflow:document.documentElement.scrollWidth>innerWidth};
  });}
  for(const font of [12,14,18,20,24])for(const width of [320,375,480,600,768,900,1280]){
    await page.setViewportSize({width,height:340});await page.evaluate(font=>fixture.render('normal',font),font);await page.waitForTimeout(80);
    const result={nativeFont:font,...await measure()};results.push(result);
    check(!result.clipped&&!result.pageOverflow&&(!result.overflow||result.fitStage===8&&result.shellOverflow),'Clipped layout: '+JSON.stringify(result));
    check(result.rows===1,'Pills wrapped: '+JSON.stringify(result));
    check(result.trackWidth>=16,'Weekly internal progress track disappeared');
    check(result.outerPadding==='0px'&&result.outerBackground==='rgba(0, 0, 0, 0)','Extra outer container or padding returned');
    check(result.pillRadius==='24px','Chips do not use native Files changed radius');
    check(result.values.length===4&&true&&result.values[1].includes('13 files changed')&&/^(Context|Ctx) 29%$/.test(result.values[3]),'Metric order or full label missing');
    check(result.values[0].includes('83%'),'Weekly did not show remaining quota');
    check(result.font===result.diffFont,'Files changed font differs from bar');
    const unit=await page.locator('.cu-unit').innerText();
    check(unit===(result.stage>=2?'tok/s':'token/s'),'Token and Context labels did not compact together');
    if(result.fitStage>=2)check(!result.values[0].includes('9h')&&result.values[0].includes('5d'),'Hours did not shorten at fit 2');
    if(result.fitStage<2)check(result.values[0].includes('5d 9h'),'Countdown shortened before fit 2');
    if(width===1280)check(result.font===font+'px','Native chat font not inherited at wide width');
  }
  await page.evaluate(()=>fixture.render('normal',14));await page.setViewportSize({width:900,height:340});await page.waitForTimeout(80);
  await page.evaluate(()=>fixture.utility(true));await page.waitForTimeout(80);
  const utilityGap=await page.evaluate(()=>document.querySelector('.fixture-utility').getBoundingClientRect().top-document.querySelector('#usage').getBoundingClientRect().bottom);
  check(utilityGap===8,'Native utility strip overlaps usage: '+utilityGap);
  check((await page.locator('.cu-speed').innerText()).includes('~22'),'Full-wait timing regression');
  await page.locator('.cu-changes button').click();check(await page.evaluate(()=>fixture.clicks)===1,'Embedded diff click disconnected');
  await page.locator('.cu-changes button').focus();await page.keyboard.press('Enter');check(await page.evaluate(()=>fixture.clicks)===2,'Embedded diff keyboard action disconnected');
  await page.locator('.cu-changes button').evaluate(el=>el.blur());
  const gap=await page.evaluate(()=>document.querySelector('.fixture-input').getBoundingClientRect().top-document.querySelector('.fixture-utility').getBoundingClientRect().bottom);
  check(gap===0,'Reference input spacing changed: '+gap);
  check(await page.locator('[data-cu-above-panel]').evaluate(el=>getComputedStyle(el).display)==='none','Empty upper panel not hidden');
  await fs.mkdir('../outputs',{recursive:true});await page.screenshot({path:'../outputs/Codex Usage Preview.png'});
  for(const state of ['normal','normal-boundary','boundary','near-low','low','depleted','missing']){
    await page.evaluate(state=>fixture.render(state),state);await page.waitForTimeout(80);
    const color=await page.locator('.cu-fill').evaluate(el=>getComputedStyle(el).backgroundColor);
    check(color===(['low','depleted'].includes(state)?'rgb(255, 73, 73)':['boundary','near-low'].includes(state)?'rgb(227, 179, 65)':'rgb(238, 238, 238)'), 'Wrong native usage color: '+state+' '+color);
  }
  await page.evaluate(()=>fixture.render('accuracy'));await page.waitForTimeout(80);
  const accuracy=await page.evaluate(()=>({text:document.querySelector('.cu-week').innerText,ratio:document.querySelector('.cu-fill').getBoundingClientRect().width/document.querySelector('.cu-track').getBoundingClientRect().width}));
  check(accuracy.text.includes('91%')&&Math.abs(accuracy.ratio-.91)<.002,'Remaining fill mismatch: '+JSON.stringify(accuracy));
  for(const width of [1280,600,375,320]){
    await page.setViewportSize({width,height:500});
    for(const utility of [false,true])for(const goal of [false,true]){
      await page.evaluate(({utility,goal})=>{fixture.render('normal');fixture.utility(utility);fixture.goal(goal);},{utility,goal});await page.waitForTimeout(60);
      const layout=await page.evaluate(()=>{const u=document.querySelector('#usage').getBoundingClientRect(),g=document.querySelector('.fixture-goal').getBoundingClientRect(),t=document.querySelector('.fixture-utility').getBoundingClientRect(),c=document.querySelector('.fixture-input').getBoundingClientRect();return{u:u.bottom,ul:u.left,uw:u.width,g:g.top,gb:g.bottom,gl:g.left,gw:g.width,cl:c.left,cw:c.width,t:t.top,tb:t.bottom,tl:t.left,tw:t.width,c:c.top};});
      if(goal){check(layout.g>=layout.u+7,'Goal above or overlapping usage');check(Math.abs(layout.ul-layout.gl)<1&&Math.abs(layout.uw-layout.gw)<1,'Usage does not match Goal width');}
      if(utility){check(Math.abs(layout.ul-layout.tl)<1&&Math.abs(layout.uw-layout.tw)<1,'Usage does not match native utility width');check(layout.t>=layout.u+7,'Utility above or overlapping usage');check(Math.abs(layout.c-layout.tb)<1,'Utility detached from composer');}
      if(goal&&utility)check(layout.t>=layout.gb,'Goal/utility overlap');
      if(!goal&&!utility)check(Math.abs(layout.ul-layout.cl-12)<1&&Math.abs(layout.uw-(layout.cw-24))<1,'Absent Goal lost its native inset');
    }
    await page.evaluate(()=>{fixture.goal(false);fixture.utility(false);});
    const labels=await measure();
    if(width===1280)check(labels.values[0].includes('left')&&labels.values[3].startsWith('Context'),'Wide labels shortened');
    if(labels.fitStage>=2)check(!labels.values[0].includes('left'),'Compact left wording not hidden');
    if(labels.stage>=2)check(labels.values[3].startsWith('Ctx'),'Compact context label not shortened');
    if(labels.fitStage>=4)check(!labels.values[2].includes('⚡'),'Compact icon not removed');
    if(labels.stage>=2)check(!labels.values[0].includes('Weekly'),'Tight weekly label not removed');
  }
  await page.evaluate(()=>document.body.style.setProperty('--color-background-primary-solid','#1654aa'));
  await page.evaluate(()=>fixture.render('normal'));await page.waitForTimeout(80);
  check(await page.locator('.cu-fill').evaluate(el=>getComputedStyle(el).backgroundColor)==='rgb(22, 84, 170)','Usage color does not follow the host theme');
  for(const state of ['missing','zero','expired','nodiff','completed','blocked','plan','fallback']){
    await page.evaluate(state=>fixture.render(state),state);await page.waitForTimeout(80);
    if(state==='fallback'){
      check(await page.locator('#native-panels button').count()===1,'Native fallback diff lost without bar');
    }else{
      check(await page.locator('#native-panels button').count()===0,'Duplicate Files changed control');
      check(await page.locator('.cu-changes button').count()===(['nodiff','completed','blocked'].includes(state)?0:1),'Conditional diff presence incorrect: '+state);
      if(state==='plan')check(await page.locator('#native-panels').innerText()==='Native plan stays above','Native plan misplaced');
      const text=await page.locator('.cu-bar').innerText();
      if(state==='missing')check(text.includes('—')&&!text.includes('0%'),'Unknown data rendered as zero');
      if(state==='zero')check(text.includes('0%'),'Actual zero hidden');
      if(state==='expired')check(text.includes('Updating'),'Expired reset not marked Updating');
    }
  }
  for(const state of ['normal','nodiff']){
    await page.setViewportSize({width:188,height:420});await page.evaluate(state=>fixture.render(state),state);await page.waitForTimeout(80);
    const result=await measure();check(result.outerPadding==='0px'&&result.outerBackground==='rgba(0, 0, 0, 0)','Outer frame returned in '+state);check(result.rows===1&&!result.clipped&&!result.pageOverflow&&(!result.overflow||result.fitStage===8&&result.shellOverflow),'Narrow effective-width overflow: '+JSON.stringify(result));
  }
  await page.setViewportSize({width:669,height:420});await page.evaluate(()=>fixture.render('normal',18));await page.waitForTimeout(60);
  await page.locator('.cu-changes button span').first().evaluate(el=>el.textContent='2 files changed');await page.waitForTimeout(60);
  let screenshotLayout=await measure();check(screenshotLayout.rows===1&&!screenshotLayout.overflow,'Reported two-line width did not fit responsively');
  await page.locator('.cu-changes button span').first().evaluate(el=>el.textContent='125 files changed');await page.waitForTimeout(60);
  screenshotLayout=await measure();check(screenshotLayout.rows===1&&!screenshotLayout.overflow,'Native diff count change caused wrapping');
  await page.setViewportSize({width:900,height:340});await page.evaluate(()=>{fixture.render('normal',14);fixture.utility(true);});await page.waitForTimeout(60);
  await page.screenshot({path:'../outputs/Codex Usage Preview.png'});
  for(const zoom of [.75,.9,1,1.1,1.25])for(const width of [375,669,900,1280])for(const reference of ['utility','goal','absent']){
    await page.setViewportSize({width,height:600});
    await page.evaluate(({zoom,reference})=>{document.body.style.zoom=zoom;document.body.style.width=`calc(100vw / ${zoom})`;fixture.render('normal',18);fixture.goal(reference==='goal');fixture.utility(reference==='utility');},{zoom,reference});
    await page.waitForTimeout(100);
    const fit=await page.evaluate(({reference,zoom})=>{
      const u=document.querySelector('#usage').getBoundingClientRect(),n=document.querySelector(reference==='goal'?'.fixture-goal':reference==='utility'?'.fixture-utility':'.fixture-input').getBoundingClientRect(),p=[...document.querySelectorAll('.cu-pill')].filter(el=>el.getBoundingClientRect().width>0),bar=document.querySelector('.cu-bar'),inset=reference==='absent'?12*zoom:0;
      return{left:u.left,right:u.right,nativeLeft:n.left+inset,nativeRight:n.right-inset,last:p.at(-1).getBoundingClientRect().right,stage:Number(bar.dataset.cuFit),rows:new Set(p.map(el=>Math.round(el.getBoundingClientRect().top))).size};
    },{reference,zoom});
    check(Math.abs(fit.left-fit.nativeLeft)<1&&Math.abs(fit.right-fit.nativeRight)<1,'Zoom applied twice or Goal edges differ: '+JSON.stringify({zoom,width,reference,...fit}));
    check(fit.rows===1,'Zoom caused wrapping');
    if(fit.stage<8)check(Math.abs(fit.last-fit.nativeRight)<1,'Pills do not fill right edge: '+JSON.stringify({zoom,width,reference,...fit}));
  }
  await page.evaluate(()=>{document.body.style.zoom='';document.body.style.width='';});
  await page.setViewportSize({width:900,height:340});await page.evaluate(()=>{fixture.render('normal',14);fixture.utility(true);});await page.waitForTimeout(80);
  // Spare width goes to every object gap and both ends, including Weekly.
  for (const state of ['normal','nodiff']) for (const width of [900,1280]) {
    await page.setViewportSize({width,height:340});
    await page.evaluate(state=>{fixture.render(state,14);fixture.utility(true);},state);await page.waitForTimeout(80);
    const spacing=await page.evaluate(()=>{
      const pills=[...document.querySelectorAll('.cu-pill')].filter(el=>el.getBoundingClientRect().width>0);
      return pills.filter(el=>!el.classList.contains('cu-changes')).map(pill=>{
        const rect=pill.getBoundingClientRect(),border=parseFloat(getComputedStyle(pill).borderLeftWidth);
        const objects=[...pill.children].filter(el=>getComputedStyle(el).display!=='none').map(el=>el.getBoundingClientRect());
        const gaps=[objects[0].left-rect.left-border,...objects.slice(1).map((r,i)=>r.left-objects[i].right),rect.right-border-objects.at(-1).right];
        return {className:pill.className,gaps};
      });
    });
    const gaps=spacing.flatMap(pill=>pill.gaps);
    check(Math.max(...gaps)-Math.min(...gaps)<1,'Object and edge spacing differs: '+JSON.stringify({state,width,spacing}));
    const allocation=await page.evaluate(async()=>{
      const {fitBar}=await import('/src/responsive.mjs'),bar=document.querySelector('.cu-bar'),track=bar.querySelector('.cu-track'),old=bar.style.width;
      fitBar(bar);const before=track.getBoundingClientRect().width;
      bar.style.width=(bar.getBoundingClientRect().width+120)+'px';fitBar(bar);const after=track.getBoundingClientRect().width;
      bar.style.width=old;fitBar(bar);return after-before;
    });
    check(Math.abs(allocation-84)<.5,'Weekly did not get 70% of spare width: '+allocation);
    check((await page.locator('.cu-unit').innerText())==='token/s','Token unit was not expanded');
  }
  const hysteresis=await page.evaluate(async()=>{
    const {fitBar}=await import('/src/responsive.mjs'),bar=document.querySelector('.cu-bar'),old=bar.style.width;
    bar.style.width='1600px';fitBar(bar);let boundary;
    for(let width=1600;width>200;width--){bar.style.width=width+'px';if(fitBar(bar)>0){boundary=width;break;}}
    const compact=Number(bar.dataset.cuFit);
    bar.style.width=(boundary+6)+'px';const buffered=fitBar(bar);
    bar.style.width=(boundary+12)+'px';const restored=fitBar(bar);
    bar.style.width=old;fitBar(bar);return{compact,buffered,restored};
  });
  check(hysteresis.compact>0&&hysteresis.buffered===hysteresis.compact&&hysteresis.restored===0,'Restore buffer failed: '+JSON.stringify(hysteresis));
  for(const width of [1280,686,375]){
    await page.setViewportSize({width,height:340});await page.evaluate(()=>fixture.render('hourly',14));await page.waitForTimeout(80);
    check((await page.locator('.cu-reset').innerText())==='13h','Hours-only countdown changed at width '+width);
  }
  await page.setViewportSize({width:900,height:340});await page.evaluate(()=>{fixture.render('normal',14);fixture.utility(true);});
  await page.waitForTimeout(80);await page.screenshot({path:'../outputs/Codex Usage Preview.png'});
  const chatBreakpoints=[];
  for(const state of ['normal','nodiff']){
    await page.setViewportSize({width:1280,height:340});await page.evaluate(state=>fixture.render(state,14),state);await page.waitForTimeout(80);
    const stages=await page.evaluate(async()=>{
      const {fitBar}=await import('/src/responsive.mjs'),bar=document.querySelector('.cu-bar'),old=bar.style.width,extra=parseFloat(getComputedStyle(bar).getPropertyValue('--cu-chat-extra'))||0,results=[];
      for(const width of [1000,662,621,620,581,580,491,490]){
        bar.style.width=(width-extra)+'px';fitBar(bar);
        results.push({chatWidth:width,stage:Number(bar.dataset.cuStage),fit:Number(bar.dataset.cuFit),weekly:getComputedStyle(bar.querySelector('.cu-week-label')).display,left:getComputedStyle(bar.querySelector('.cu-left')).display,unit:bar.querySelector('.cu-unit').innerText,reset:bar.querySelector('.cu-reset').innerText});
      }
      bar.style.width=old;fitBar(bar);return results;
    });
    for(const row of stages){
      const expected=row.chatWidth<=490?3:row.chatWidth<=580?2:row.chatWidth<=620?1:0;
      check(state==='nodiff'?row.stage===expected:row.stage>=expected,'Chat breakpoint differs: '+JSON.stringify({state,row,expected}));
      check((row.weekly==='none')===(row.stage>=2),'Weekly did not hide at Stage 2');
      check((row.left==='none')===(row.fit>=2),'Left did not hide at fit 2');
      check(row.unit===(row.stage>=2?'tok/s':'token/s'),'Paired compact unit broke');
      check(row.reset===(row.fit>=2?'5d':'5d 9h'),'Countdown compacted at wrong stage: '+JSON.stringify({state,row}));
    }
    chatBreakpoints.push({state,stages});
  }
  await page.setViewportSize({width:900,height:340});await page.evaluate(()=>{fixture.render('normal',14);fixture.utility(true);});await page.waitForTimeout(80);
  const goalPriority=await page.evaluate(()=>{
    fixture.goal(true);fixture.utility(true);const utility=document.querySelector('.fixture-utility');utility.style.left='24px';utility.style.right='24px';
  });
  await page.waitForTimeout(80);
  check(await page.evaluate(()=>Math.abs(document.querySelector('#usage').getBoundingClientRect().width-document.querySelector('.fixture-goal').getBoundingClientRect().width)<1),'Goal lost width priority to utility');
  await page.evaluate(()=>{const utility=document.querySelector('.fixture-utility');utility.style.left='';utility.style.right='';fixture.goal(false);});await page.waitForTimeout(80);
  // Native Appearance changes and delayed selected fonts can widen text while
  // the bar's own width, font size and line height stay unchanged.
  const fontChanges=[];
  for (const width of [900,500]) for (const delayed of [false,true]) {
    await page.setViewportSize({width,height:340});
    await page.evaluate(delayed=>{
      fixture.utility(false);fixture.render('normal',14);
      document.body.style.fontFamily=delayed?'"Codex Usage Delayed Font", Arial':'Arial';
    },delayed);await page.waitForTimeout(80);
    const before=await measure();
    const changed=await page.evaluate(async delayed=>{
      const object=document.querySelector('.cu-speed .cu-value'),before=object.getBoundingClientRect().width;
      if(delayed){
        const font=await new FontFace('Codex Usage Delayed Font','local("Courier New")').load();
        document.fonts.add(font);window.fixtureDelayedFont=font;
      }else document.body.style.fontFamily='monospace';
      return {before,after:object.getBoundingClientRect().width};
    },delayed);await page.waitForTimeout(100);
    const after=await measure();
    check(Math.abs(changed.before-changed.after)>.1,'Font regression did not change text metrics');
    check(after.barWidth===before.barWidth&&after.rows===1&&!after.overflow&&!after.clipped&&!after.pageOverflow,
      'Inherited font change was not fitted: '+JSON.stringify({width,delayed,before,after}));
    fontChanges.push({width,delayed,fitStage:after.fitStage});
    await page.evaluate(()=>{
      document.body.style.fontFamily='';
      if(window.fixtureDelayedFont){document.fonts.delete(window.fixtureDelayedFont);delete window.fixtureDelayedFont;}
    });await page.waitForTimeout(80);
  }
  await page.setViewportSize({width:900,height:340});await page.evaluate(()=>{fixture.render('normal',14);fixture.utility(true);});await page.waitForTimeout(80);
  const idleWrites=await page.evaluate(async()=>{
    let writes=0;const bar=document.querySelector('.cu-bar'),observer=new MutationObserver(records=>writes+=records.length);
    observer.observe(bar,{attributes:true,attributeFilter:['style']});await new Promise(resolve=>setTimeout(resolve,250));observer.disconnect();return writes;
  });
  check(idleWrites===0,'Responsive/native observers kept refitting an idle bar: '+idleWrites);
  check(!errors.length,errors.join('\n'));
  await fs.writeFile('../outputs/Layout Verification.json',JSON.stringify({results,zoomLayouts:60,equalObjectSpacing:true,weeklySpareShare:0.70,responsiveStages:3,goalWidthFallback:true,chatBreakpoints,fontChanges,states:8,nativeColors:true,utilityGap,narrowEffectiveWidth:188,inputGap:gap,errors},null,2)+'\n');
  console.log(JSON.stringify({layouts:results.length,zoomLayouts:60,equalObjectSpacing:true,weeklySpareShare:0.70,responsiveStages:3,goalWidthFallback:true,chatBreakpoints,fontChanges,nativeFontSizes:[12,14,18,20,24],widths:[320,375,480,600,768,900,1280],states:8,nativeColors:true,utilityGap,portalClickAndKeyboard:true,nativeFallback:true,inputGap:gap,narrowEffectiveWidth:188,errors}));
}finally{await browser?.close();server.kill();}
