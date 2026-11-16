// Pure Node VM/DOM-stub tests; not browser automation, network access, or factual fixtures.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();
function node(tag='div'){return{tagName:tag.toUpperCase(),value:'',checked:false,children:[],attrs:{},hidden:false,disabled:false,open:false,classList:{add(){},remove(){},toggle(){}},setAttribute(k,v){this.attrs[k]=v;if(k==='value')this.value=v;},append(...items){this.children.push(...items.map(x=>typeof x==='string'?{textContent:x}:x));},replaceChildren(...items){this.children=[];this.append(...items);},get textContent(){return this._text||this.children.map(x=>x.textContent||'').join('');},set textContent(v){this._text=String(v);this.children=[];},addEventListener(){},showModal(){this.open=true},close(){this.open=false},focus(){}};}
function el(id){if(!elements.has(id))elements.set(id,node());return elements.get(id);}
const document={getElementById:el,createElement:node,createTextNode:t=>({textContent:String(t)}),querySelectorAll(){return[]},addEventListener(){},activeElement:{tagName:'BODY'}};
const context=vm.createContext({document,localStorage:{getItem:()=>null,setItem(){}},console,URL,Intl,setTimeout,clearTimeout,fetch:async()=>{throw Error('No network in synthetic tests')}});
let code=fs.readFileSync('web/app.js','utf8').replace(/load\(\);\s*$/,'');vm.runInContext(code,context);
const run=s=>vm.runInContext(s,context);el('metric').value='r';el('max').value='1000';
run(`projects=[{s:'fixture-one',n:'SYNTHETIC Invoice',d:'Synthetic invoice',m:1,r:10,t:10,c:[],v:'D',a:['rounded','rounded','rounded'],_search:'synthetic invoice'},{s:'fixture-zero',n:'SYNTHETIC Zero',d:'Synthetic',m:0,r:0,t:0,c:[],v:'D',a:[],_search:'synthetic zero'},{s:'fixture-unknown',n:'SYNTHETIC Unknown',d:'Synthetic',m:null,r:null,t:null,c:[],v:'R',a:[],_search:'synthetic unknown'}]; applyFilters();`);
assert.equal(run('filtered.length'),1);run(`setPreset('all')`);assert.equal(run('filtered.length'),3);el('search').value='发票';run('applyFilters()');assert.equal(run('filtered.length'),1);
assert.equal(run(`safeURL('javascript:alert(1)')`),null);assert.equal(run(`safeURL('data:text/html,unsafe')`),null);assert.equal(run(`safeURL('https://user:pass@example.invalid/')`),null);assert.equal(run(`safeURL('https://example.invalid/?api_key=synthetic')`),null);assert.equal(run(`el('span',{},'<img onerror=1>').textContent`),'<img onerror=1>');
assert.ok(run('money(0).textContent').includes('$0'));assert.ok(run('money(null).textContent').includes('未知'));assert.ok(run(`money(10,'directory_display_rounded_or_unknown').textContent`).includes('≈'));
run(`setPreset('saved')`);assert.equal(run('filtered.length'),0);run(`toggleSaved('fixture-one')`);assert.equal(run('filtered.length'),1);
console.log('12 frontend assertions passed: filtering, Chinese search synonyms, null/zero, source precision, safe links, escaping and local favorites.');
