// Pure Node VM/DOM-stub tests; not browser automation, network access, or factual fixtures.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();
function node(tag='div'){return{tagName:tag.toUpperCase(),value:'',checked:false,children:[],attrs:{},hidden:false,disabled:false,open:false,classList:{add(){},remove(){},toggle(){}},setAttribute(k,v){this.attrs[k]=v;if(k==='value')this.value=v;},append(...items){this.children.push(...items.map(x=>typeof x==='string'?{textContent:x}:x));},replaceChildren(...items){this.children=[];this.append(...items);},get textContent(){return this._text||this.children.map(x=>x.textContent||'').join('');},set textContent(v){this._text=String(v);this.children=[];},addEventListener(){},showModal(){this.open=true},close(){this.open=false},focus(){}};}
function el(id){if(!elements.has(id))elements.set(id,node());return elements.get(id);}
const document={getElementById:el,createElement:node,createTextNode:t=>({textContent:String(t)}),querySelectorAll(){return[]},addEventListener(){},activeElement:{tagName:'BODY'}};
const context=vm.createContext({document,localStorage:{getItem:()=>null,setItem(){}},console,URL,Intl,setTimeout,clearTimeout,fetch:async()=>{throw Error('No network in synthetic tests')}});
let code=fs.readFileSync('web/app.js','utf8').replace(/load\(\);\s*$/,'');vm.runInContext(code,context);
const run=s=>vm.runInContext(s,context);el('age').value='all';el('metric').value='r';el('max').value='1000';
run(`projects=[{s:'fixture-one',n:'SYNTHETIC Invoice',d:'Synthetic invoice',m:1,r:10,t:10,c:[],v:'D',a:['rounded','rounded','rounded'],_search:'synthetic invoice'},{s:'fixture-zero',n:'SYNTHETIC Zero',d:'Synthetic',m:0,r:0,t:0,c:[],v:'D',a:[],_search:'synthetic zero'},{s:'fixture-unknown',n:'SYNTHETIC Unknown',d:'Synthetic',m:null,r:null,t:null,c:[],v:'R',a:[],_search:'synthetic unknown'}]; applyFilters();`);
assert.equal(run('filtered.length'),1);run(`setPreset('all')`);assert.equal(run('filtered.length'),3);el('search').value='发票';run('applyFilters()');assert.equal(run('filtered.length'),1);
assert.equal(run(`safeURL('javascript:alert(1)')`),null);assert.equal(run(`safeURL('data:text/html,unsafe')`),null);assert.equal(run(`safeURL('https://user:pass@example.invalid/')`),null);assert.equal(run(`safeURL('https://example.invalid/?api_key=synthetic')`),null);assert.equal(run(`el('span',{},'<img onerror=1>').textContent`),'<img onerror=1>');
assert.ok(run('money(0).textContent').includes('$0'));assert.ok(run('money(null).textContent').includes('未知'));assert.ok(run(`money(10,'directory_display_rounded_or_unknown').textContent`).includes('≈'));
run(`setPreset('saved')`);assert.equal(run('filtered.length'),0);run(`toggleSaved('fixture-one')`);assert.equal(run('filtered.length'),1);
console.log('Base filtering/security checks passed; testing rolling-year evidence next.');

// Synthetic rolling-year cases: no invented launch dates or GMV/MRR-only payment claims.
const win=run(`rollingWindow(new Date('2026-11-16T08:00:00Z'))`);
assert.equal(new Date(win[0]).toISOString().slice(0,10),'2025-11-16');
assert.equal(run(`matchesAge({ld:'2026-10（月）',le:true,r:10,t:10},'recent',[Date.UTC(2025,10,16),Date.UTC(2026,10,16)])`),true);
assert.equal(run(`matchesAge({ld:'2025-11（月）',le:true,r:10},'recent',[Date.UTC(2025,10,16),Date.UTC(2026,10,16)])`),false);
assert.equal(run(`matchesAge({ld:'2026-12-01',le:true,r:10},'recent',[Date.UTC(2025,10,16),Date.UTC(2026,10,16)])`),false);
assert.equal(run(`matchesAge({ld:'2026-10-01',le:false,r:10},'recent')`),false);
assert.equal(run(`matchesAge({fd:'2026-10-01',r:10},'recent')`),false);
assert.equal(run(`matchesAge({fd:'2026-10-01',r:10},'founded',[Date.UTC(2025,10,16),Date.UTC(2026,10,16)])`),true);
assert.equal(run(`matchesAge({ld:'2020-01-01',le:true,fd:'2026-10-01',r:10},'founded')`),false);
assert.equal(run(`hasPayment({m:100,r:0,t:null,gmv:10000})`),false);
assert.equal(run(`hasPayment({r:0,t:10})`),true);
assert.equal(run(`dateBounds('2026-02-30')`),null);
assert.equal(run(`matchesAge({fd:'2026-10-01',r:10},'unknown')`),true);
assert.equal(run(`matchesAge({ld:'2020-01-01',le:true,r:10},'all')`),true);
console.log('26 frontend assertions passed, including rolling 12-month evidence/precision, founder-date separation, future dates and non-GMV payment.');
