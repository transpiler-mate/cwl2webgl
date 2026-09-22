/* Native WebGL geometry, with a Canvas2D text overlay and accessible HTML controls.
 * No remote dependencies, network requests, eval, or injected HTML. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('payload').textContent);
  const $ = id => document.getElementById(id);
  const colors = {input: [0.39, 0.85, 0.75], step: [0.45, 0.71, 1], workflow: [0.77, 0.61, 1], output: [0.96, 0.73, 0.45]};
  const canvas = $('graph'), labels = $('labels'), stage = $('stage');
  const text = labels.getContext('2d');
  let gl = canvas.getContext('webgl', {alpha: true, antialias: true});
  let program, buffer, position, color;
  let view, current, selected = null, stack = [], points = new Map(), scale = 1, tx = 0, ty = 0;
  let width = 0, height = 0, frame = 0, drag = null, moved = false;
  const layouts = new Map();
  function error(message) { $('error').hidden = false; $('error').textContent = message; }
  function shader(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source); gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw Error(gl.getShaderInfoLog(shader));
    return shader;
  }
  function initGL() {
    if (!gl) { error('WebGL is unavailable. The node list, contracts and subworkflow navigation remain available. Enable hardware acceleration to view the graph.'); return; }
    program = gl.createProgram();
    gl.attachShader(program, shader(gl.VERTEX_SHADER, 'attribute vec2 p; attribute vec3 c; varying vec3 v; void main(){gl_Position=vec4(p,0.0,1.0);v=c;}'));
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, 'precision mediump float; varying vec3 v; void main(){gl_FragColor=vec4(v,1.0);}'));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error(gl.getProgramInfoLog(program));
    position = gl.getAttribLocation(program, 'p'); color = gl.getAttribLocation(program, 'c'); buffer = gl.createBuffer();
  }
  try { initGL(); } catch (exc) { error('Cannot initialize WebGL: ' + exc.message); gl = null; }
  canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); gl = null; error('The graphics context was lost. Reload to restore the graph; the inspector still works.'); });
  function short(id) { return id.split(/[\/#]/).pop(); }
  function option(parent, value, label) { const o = document.createElement('option'); o.value = value; o.textContent = label; parent.append(o); }
  function button(parent, label, action, active = false) { const b = document.createElement('button'); b.textContent = label; b.onclick = action; b.classList.toggle('active', active); parent.append(b); return b; }
  function schedule() { if (!frame) frame = requestAnimationFrame(() => { frame = 0; draw(); }); }
  function layout() {
    const incoming = new Map(view.nodes.map(n => [n.id, new Set()]));
    const outgoing = new Map(view.nodes.map(n => [n.id, new Set()]));
    for (const e of view.edges) { incoming.get(e.target).add(e.source); outgoing.get(e.source).add(e.target); }
    const degree = new Map([...incoming].map(([id, set]) => [id, set.size]));
    const level = new Map(view.nodes.map(n => [n.id, 0]));
    const queue = view.nodes.filter(n => !degree.get(n.id)).map(n => n.id);
    let visited = 0;
    for (let i = 0; i < queue.length; i++) {
      const id = queue[i]; visited++;
      for (const next of outgoing.get(id)) {
        level.set(next, Math.max(level.get(next), level.get(id) + 1));
        degree.set(next, degree.get(next) - 1); if (!degree.get(next)) queue.push(next);
      }
    }
    if (visited !== view.nodes.length) error('Cyclic dependencies detected. Layout is approximate; inspect the CWL connections.');
    const columns = new Map();
    for (const n of view.nodes) { const l = level.get(n.id); if (!columns.has(l)) columns.set(l, []); columns.get(l).push(n); }
    points = new Map();
    for (const [column, nodes] of columns) nodes.forEach((n, row) => points.set(n.id, {x: column * 330, y: (row - (nodes.length - 1) / 2) * 140}));
  }
  function resize() {
    width = stage.clientWidth; height = stage.clientHeight;
    const dpr = window.devicePixelRatio || 1;
    for (const c of [canvas, labels]) { c.width = Math.round(width * dpr); c.height = Math.round(height * dpr); }
    text.setTransform(dpr, 0, 0, dpr, 0, 0); schedule();
  }
  function fit() {
    const all = [...points.values()];
    const xs = all.map(p => p.x), ys = all.map(p => p.y);
    const minX = all.length ? Math.min(...xs) : 0, maxX = all.length ? Math.max(...xs) : 0;
    const minY = all.length ? Math.min(...ys) : 0, maxY = all.length ? Math.max(...ys) : 0;
    scale = Math.max(0.02, Math.min(1.3, (width - 100) / (maxX - minX + 260), (height - 140) / (maxY - minY + 100)));
    tx = width / 2 - (minX + maxX) / 2 * scale; ty = height / 2 - (minY + maxY) / 2 * scale;
    schedule();
  }
  function screen(id) { const p = points.get(id); return {x: p.x * scale + tx, y: p.y * scale + ty}; }
  function elide(label, limit) {
    if (text.measureText(label).width <= limit) return label;
    while (label.length && text.measureText(label + '…').width > limit) label = label.slice(0, -1);
    return label + '…';
  }
  // The same convex outline is used to draw, hit-test and clip connections.
  function shape(node, inset = 0) {
    const p = screen(node.id), w = 114 - inset, h = 43 - inset;
    let vertices;
    if (node.kind === 'input') vertices = [{x: -w + 18, y: -h}, {x: w, y: -h}, {x: w - 18, y: h}, {x: -w, y: h}];
    else if (node.kind === 'output') vertices = [{x: -w + 18, y: -h}, {x: w - 18, y: -h}, {x: w, y: 0}, {x: w - 18, y: h}, {x: -w + 18, y: h}, {x: -w, y: 0}];
    else {
      vertices = []; const radius = 12;
      for (const [cx, cy, start] of [[w-radius, -h+radius, -90], [w-radius, h-radius, 0], [-w+radius, h-radius, 90], [-w+radius, -h+radius, 180]]) {
        for (let i = 0; i <= 6; i++) { const angle = (start + i * 15) * Math.PI / 180; vertices.push({x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle)}); }
      }
    }
    return vertices.map(v => ({x: p.x + v.x * scale, y: p.y + v.y * scale}));
  }
  function cross(a, b) { return a.x * b.y - a.y * b.x; }
  function boundary(center, towards, polygon) {
    const d = {x: towards.x - center.x, y: towards.y - center.y};
    for (let i = 0; i < polygon.length; i++) {
      const a = polygon[i], b = polygon[(i + 1) % polygon.length];
      const edge = {x: b.x - a.x, y: b.y - a.y}, offset = {x: a.x - center.x, y: a.y - center.y};
      const denominator = cross(d, edge); if (Math.abs(denominator) < 1e-9) continue;
      const t = cross(offset, edge) / denominator, u = cross(offset, d) / denominator;
      if (t >= 0 && u >= -1e-9 && u <= 1 + 1e-9) return {x: center.x + t * d.x, y: center.y + t * d.y};
    }
    return center;
  }
  function hitTest(x, y) {
    // Reverse draw order: a card on top gets the pointer first.
    return [...view.nodes].reverse().find(n => {
      const polygon = shape(n);
      return polygon.every((a, i) => {
        const b = polygon[(i + 1) % polygon.length];
        return cross({x: b.x - a.x, y: b.y - a.y}, {x: x - a.x, y: y - a.y}) >= -1e-6;
      });
    });
  }
  function tracing() {
    if (!selected) return {nodes: new Set(view.nodes.map(n => n.id)), edges: new Set(view.edges)};
    const nodes = new Set([selected]), edges = new Set(), mode = $('direction').value;
    const walk = reverse => {
      const seen = new Set([selected]), queue = [selected];
      const adjacency = new Map();
      for (const e of view.edges) { const from = reverse ? e.target : e.source; if (!adjacency.has(from)) adjacency.set(from, []); adjacency.get(from).push(e); }
      for (let i = 0; i < queue.length; i++) for (const e of adjacency.get(queue[i]) || []) {
        edges.add(e); const next = reverse ? e.source : e.target; nodes.add(next);
        if (!seen.has(next)) { seen.add(next); queue.push(next); }
      }
    };
    if (mode === 'both' || mode === 'up') walk(true);
    if (mode === 'both' || mode === 'down') walk(false);
    return {nodes, edges};
  }
  function draw() {
    if (!view || !width || !height) return;
    text.clearRect(0, 0, width, height);
    if (!gl) return;
    const vertices = [], trace = tracing(), query = $('search').value.toLowerCase();
    const vertex = (p, c) => vertices.push(p.x / width * 2 - 1, 1 - p.y / height * 2, ...c);
    const triangle = (a, b, c, rgb) => { vertex(a, rgb); vertex(b, rgb); vertex(c, rgb); };
    const line = (a, b, rgb, thickness) => {
      const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
      const nx = -dy / len * thickness / 2, ny = dx / len * thickness / 2;
      const p = {x: a.x + nx, y: a.y + ny}, q = {x: a.x - nx, y: a.y - ny};
      const r = {x: b.x + nx, y: b.y + ny}, s = {x: b.x - nx, y: b.y - ny};
      triangle(p, q, r, rgb); triangle(q, r, s, rgb);
    };
    const polygons = new Map(view.nodes.map(n => [n.id, shape(n)]));
    for (const e of view.edges) {
      const source = screen(e.source), target = screen(e.target);
      if (Math.hypot(target.x - source.x, target.y - source.y) < 1) continue;
      const a = boundary(source, target, polygons.get(e.source));
      const b = boundary(target, source, polygons.get(e.target));
      // Suppress the segment while cards overlap instead of drawing inverted arrows.
      if ((b.x - a.x) * (target.x - source.x) + (b.y - a.y) * (target.y - source.y) <= 0) continue;
      const angle = Math.atan2(b.y - a.y, b.x - a.x);
      const rgb = trace.edges.has(e) ? [0.35, 0.56, 0.66] : [0.13, 0.2, 0.28];
      line(a, b, rgb, 1.5);
      triangle(b, {x: b.x - 10 * Math.cos(angle - .45), y: b.y - 10 * Math.sin(angle - .45)}, {x: b.x - 10 * Math.cos(angle + .45), y: b.y - 10 * Math.sin(angle + .45)}, rgb);
    }
    const outline = (polygon, rgb, thickness = 1.5) => polygon.forEach((p, i) => line(p, polygon[(i + 1) % polygon.length], rgb, thickness));
    for (const n of view.nodes) {
      const p = screen(n.id); if (p.x < -260 * scale || p.x > width + 260 * scale || p.y < -100 * scale || p.y > height + 100 * scale) continue;
      const match = !query || (n.label + ' ' + n.cwlId).toLowerCase().includes(query);
      const bright = trace.nodes.has(n.id) && match;
      const rgb = colors[n.kind].map(v => v * (bright ? 1 : .35));
      const polygon = polygons.get(n.id);
      const fill = rgb.map(v => v * .18);
      polygon.forEach((a, i) => triangle(p, a, polygon[(i + 1) % polygon.length], fill));
      outline(polygon, selected === n.id ? [.8, 1, .95] : rgb, selected === n.id ? 3 : 1.5);
      if (n.kind === 'workflow') outline(shape(n, 5), rgb, 1);
      if (n.kind === 'step' || n.kind === 'workflow') {
        line({x: p.x - 109 * scale, y: p.y - 8 * scale}, {x: p.x + 109 * scale, y: p.y - 8 * scale}, rgb, 1);
      }
      if (scale > .2 || selected === n.id) {
        text.save(); text.translate(p.x, p.y); text.scale(scale, scale);
        text.textAlign = 'center'; text.textBaseline = 'middle';
        text.fillStyle = bright ? '#deebf7' : '#687e93'; text.font = '600 12px system-ui';
        const label = elide(short(n.cwlId), n.kind === 'input' || n.kind === 'output' ? 174 : 200);
        text.fillText(label, 0, -23);
        text.font = '11px system-ui';
        text.fillText(elide(n.label, 178), 0, 6);
        text.font = '9px system-ui'; text.fillStyle = bright ? '#9fbbcd' : '#526a7b';
        const badges = [n.kind === 'workflow' ? 'SUBWORKFLOW' : n.kind === 'step' ? 'TOOL' : n.kind.toUpperCase(), n.details.scatter ? 'SCATTER' : '', n.details.when !== undefined ? 'WHEN' : ''].filter(Boolean);
        text.fillText(badges.join(' · '), 0, 26);
        text.restore();
      }
    }
    gl.viewport(0, 0, canvas.width, canvas.height); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(program); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 20, 0);
    gl.enableVertexAttribArray(color); gl.vertexAttribPointer(color, 3, gl.FLOAT, false, 20, 8);
    gl.drawArrays(gl.TRIANGLES, 0, vertices.length / 5);
  }
  function populateNodes() {
    $('nodes').replaceChildren(); const query = $('search').value.toLowerCase();
    const visible = view.nodes.filter(n => (n.label + ' ' + n.id).toLowerCase().includes(query));
    $('count').textContent = '(' + visible.length + ')';
    for (const n of visible) button($('nodes'), n.label + ' · ' + n.kind, () => select(n.id), selected === n.id);
  }
  function inspect(info) {
    $('properties').replaceChildren(); option($('properties'), '', 'All fields');
    const fields = Object.keys(info); fields.forEach((key, index) => option($('properties'), String(index), key));
    const show = () => { const v = $('properties').value; $('detail').textContent = JSON.stringify(v === '' ? info : info[fields[Number(v)]], null, 2); };
    $('properties').onchange = show; show();
  }
  function select(id) {
    selected = id; const n = view.nodes.find(n => n.id === id);
    $('selection').textContent = n ? n.label : view.label;
    $('summary').textContent = n ? n.kind + ' · ' + n.cwlId : view.nodes.length + ' nodes · ' + view.edges.length + ' connections';
    $('open').hidden = !n || !n.child;
    $('open').onclick = () => { if (n && n.child) { stack.push({key: current, label: n.label}); load(n.child); } };
    inspect(n ? n.details : view.details); $('connections').replaceChildren();
    for (const edge of view.edges.filter(e => !n || e.source === id || e.target === id)) {
      button($('connections'), short(edge.sourcePort) + ' → ' + short(edge.targetPort), () => inspect({...edge, source: view.nodes.find(item => item.id === edge.source).cwlId, target: view.nodes.find(item => item.id === edge.target).cwlId}));
    }
    populateNodes(); schedule();
  }
  function load(key) {
    cancelDrag(true);
    if (current) layouts.set(current, {points, scale, tx, ty});
    current = key; view = data.views[key]; selected = null; $('search').value = '';
    $('back').disabled = !stack.length;
    $('breadcrumb').textContent = [...stack.map(item => item.label), view.label].join(' / ');
    const saved = layouts.get(key);
    if (saved) { ({points, scale, tx, ty} = saved); select(null); }
    else { layout(); select(null); fit(); }
  }
  $('title').textContent = data.title; document.title = data.title;
  for (const key of data.roots) option($('workflows'), key, data.views[key].label + ' · ' + data.views[key].id);
  $('workflows').onchange = () => { stack = []; load($('workflows').value); };
  $('back').onclick = () => { const previous = stack.pop(); if (previous) load(previous.key); };
  $('reset').onclick = () => { cancelDrag(true); layout(); fit(); };
  $('fit').onclick = fit; $('direction').onchange = schedule;
  $('search').oninput = () => { populateNodes(); schedule(); };
  function localPointer(event) { const rect = canvas.getBoundingClientRect(); return {x: event.clientX - rect.left, y: event.clientY - rect.top}; }
  function cancelDrag(restore = false) {
    if (!drag) return;
    const previous = drag; drag = null;
    if (restore) {
      if (previous.node) points.set(previous.node, {...previous.point});
      else { tx = previous.tx; ty = previous.ty; }
    }
    if (canvas.hasPointerCapture(previous.pointer)) canvas.releasePointerCapture(previous.pointer);
    canvas.style.cursor = 'grab'; schedule();
  }
  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0 || drag) return;
    const p = localPointer(event), hit = hitTest(p.x, p.y);
    canvas.setPointerCapture(event.pointerId);
    drag = {pointer: event.pointerId, x: event.clientX, y: event.clientY, tx, ty, node: hit ? hit.id : null, point: hit ? {...points.get(hit.id)} : null};
    moved = false; canvas.style.cursor = 'grabbing';
    if (hit) select(hit.id);
  });
  canvas.addEventListener('pointermove', event => {
    if (!drag) { const p = localPointer(event); canvas.style.cursor = hitTest(p.x, p.y) ? 'move' : 'grab'; return; }
    if (event.pointerId !== drag.pointer) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    moved ||= Math.hypot(dx, dy) > 4;
    if (!moved) return;
    if (drag.node) points.set(drag.node, {x: drag.point.x + dx / scale, y: drag.point.y + dy / scale});
    else { tx = drag.tx + dx; ty = drag.ty + dy; }
    schedule();
  });
  canvas.addEventListener('pointerup', event => {
    if (!drag || event.pointerId !== drag.pointer) return;
    const clickedBackground = !moved && !drag.node;
    cancelDrag(); if (clickedBackground) select(null);
  });
  canvas.addEventListener('pointercancel', event => { if (drag && event.pointerId === drag.pointer) cancelDrag(true); });
  canvas.addEventListener('lostpointercapture', event => { if (drag && event.pointerId === drag.pointer) cancelDrag(true); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') cancelDrag(true); });
  canvas.addEventListener('wheel', event => { event.preventDefault(); if (drag) return; const rect = canvas.getBoundingClientRect(); const x = event.clientX - rect.left, y = event.clientY - rect.top;
    const next = Math.max(.02, Math.min(6, scale * Math.exp(-event.deltaY * .001))); tx = x - (x - tx) * next / scale; ty = y - (y - ty) * next / scale; scale = next; schedule();
  }, {passive: false});
  new ResizeObserver(resize).observe(stage); resize(); load(data.roots[0]);
})();
