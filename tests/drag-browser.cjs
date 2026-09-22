// Real pointer regressions using the text overlay's coordinates; no production test API.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || undefined, headless:true,
    args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:2});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(() => {
      window.drawnLabels = {};
      const fill = CanvasRenderingContext2D.prototype.fillText;
      CanvasRenderingContext2D.prototype.fillText = function(text, x, y, ...rest) {
        if (this.canvas.id === 'labels') {
          const t=this.getTransform(), r=window.devicePixelRatio;
          // Store each card's center, independent of label baseline offset.
          window.drawnLabels[text]={x:t.e/r,y:t.f/r,scale:t.a/r};
        }
        return fill.call(this,text,x,y,...rest);
      };
    });
    await page.goto(pathToFileURL(path.resolve(process.argv[2] || 'examples/pattern-12.html')).href);
    await page.waitForFunction(()=>window.drawnLabels.node_crop);
    const flush=()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    const snapshot=()=>page.evaluate(()=>({crop:drawnLabels.node_crop,otsu:drawnLabels.node_otsu,band:drawnLabels.bands}));
    const rect=await page.locator('#graph').boundingBox();
    const moveTo=async p=>page.mouse.move(rect.x+p.x,rect.y+p.y);
    const drag=async(p,dx,dy)=>{await moveTo(p);await page.mouse.down();await page.mouse.move(rect.x+p.x+dx,rect.y+p.y+dy,{steps:6});await page.mouse.up();await flush();};
    const delta=(a,b,x,y)=>{assert.ok(Math.abs(b.x-a.x-x)<1.5,`${b.x-a.x} != ${x}`);assert.ok(Math.abs(b.y-a.y-y)<1.5,`${b.y-a.y} != ${y}`);};
    const initial=await snapshot();
    await drag(initial.crop,55,-40);
    let changed=await snapshot(); delta(initial.crop,changed.crop,55,-40); delta(initial.otsu,changed.otsu,0,0); delta(initial.band,changed.band,0,0);
    assert.equal(await page.locator('#selection').textContent(),'node_crop');
    // Zoomed movement must use CSS pixels, independent of device pixel ratio.
    await moveTo(changed.crop);await page.mouse.wheel(0,-240);await flush();
    const zoomed=await snapshot();await drag(zoomed.crop,-35,28);
    changed=await snapshot();delta(zoomed.crop,changed.crop,-35,28);delta(zoomed.otsu,changed.otsu,0,0);
    // Background pan moves every node together.
    const beforePan=await snapshot();await drag({x:rect.width-25,y:rect.height-100},20,25);changed=await snapshot();
    for(const key of ['crop','otsu','band'])delta(beforePan[key],changed[key],20,25);
    // Escape cancels an in-flight node move and releases capture.
    const beforeEscape=await snapshot();await moveTo(beforeEscape.crop);await page.mouse.down();
    await page.mouse.move(rect.x+beforeEscape.crop.x+30,rect.y+beforeEscape.crop.y+25,{steps:4});
    await page.keyboard.press('Escape');await page.mouse.up();await flush();changed=await snapshot();delta(beforeEscape.crop,changed.crop,0,0);
    // Pointer cancellation restores the dragged node as well.
    await moveTo(changed.crop);await page.mouse.down();await page.mouse.move(rect.x+changed.crop.x+30,rect.y+changed.crop.y+25,{steps:3});
    await page.locator('#graph').dispatchEvent('pointercancel',{pointerId:1});await page.mouse.up();await flush();
    delta(changed.crop,(await snapshot()).crop,0,0);
    await page.locator('#reset').click();await flush();changed=await snapshot();
    for(const key of ['crop','otsu','band'])delta(initial[key],changed[key],0,0);
    assert.equal(await page.locator('#error').isVisible(),false);assert.deepEqual(errors,[]);
    await page.mouse.click(rect.x+40,rect.y+90);await flush();
    await page.screenshot({path:process.env.SCREENSHOT_PATH || 'pattern-12-preview.png',fullPage:true});
    console.log('PASS: Pattern 12 node dragging, fixed neighbors, zoom + DPR=2, background pan, Escape, pointer cancellation and reset');
    // Navigation preserves a caller's edited layout.
    await page.goto(pathToFileURL(path.resolve('examples/atlas.html')).href);
    await page.waitForFunction(()=>window.drawnLabels.process);
    let center=await page.evaluate(()=>drawnLabels.process);await drag(center,40,-20);await flush();
    const edited=await page.evaluate(()=>drawnLabels.process);
    await page.locator('#open').click();await page.locator('#back').click();await flush();
    const returned=await page.evaluate(()=>drawnLabels.process);delta(edited,returned,0,0);
    console.log('PASS: nested navigation preserves edited positions');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
