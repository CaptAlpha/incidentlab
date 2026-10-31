'use strict';
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let investigations = [], active = null;
function notice(message, error=false) { $('#notice').textContent=message; $('#notice').className=error?'error':''; }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function tab(name) {
  for (const b of document.querySelectorAll('[data-tab]')) {b.classList.toggle('selected',b.dataset.tab===name);b.setAttribute('aria-selected',String(b.dataset.tab===name));}
  for(const n of ['findings','timeline','evidence']) $('#'+n).hidden=n!==name;
}
function renderQueue() {
  const query=$('#search').value.toLowerCase();
  const filtered=investigations.filter(r=>(r.title+' '+r.services.join(' ')+' '+r.id).toLowerCase().includes(query));
  $('#queue').innerHTML=filtered.length?filtered.map(r=>`<button class="queue-row ${active?.id===r.id?'chosen':''}" data-id="${esc(r.id)}"><span class="badge ${esc(r.severity)}">${esc(r.severity)}</span><span class="queue-main"><strong>${esc(r.title)}</strong><small>${esc(r.id)} &nbsp;·&nbsp; ${esc(r.services.join(', '))}</small></span><span class="row-count">${r.evidence_count} records &nbsp; ${r.findings.length} findings &nbsp; →</span></button>`).join(''):`<div class="empty">${query?'No matching investigations.':'Your next investigation starts here. Replay a scenario above to explore the evidence.'}</div>`;
}
async function refresh() {
  investigations=await api('/api/investigations');
  const pad=v=>String(v).padStart(2,'0');
  $('#total').textContent=pad(investigations.length);
  $('#services').textContent=pad(new Set(investigations.flatMap(r=>r.services)).size);
  $('#records').textContent=pad(investigations.reduce((n,r)=>n+r.evidence_count,0));
  $('#navCount').textContent=$('#queueCount').textContent=investigations.length;
  renderQueue();
}
function evidenceList() {
  if(!active) return;
  const query=$('#evidenceSearch').value.toLowerCase();
  const records=active.evidence.filter(e=>JSON.stringify(e).toLowerCase().includes(query));
  $('#evidenceList').innerHTML=records.length?records.map(e=>`<details id="${esc(e.id)}"><summary><code>${esc(e.id)}</code> ${esc(e.summary)} <span class="confidence">· ${esc(e.service)}</span></summary><pre>${esc(JSON.stringify(e.raw,null,2))}</pre></details>`).join(''):'<p>No evidence matches this filter.</p>';
}
function show(result) {
  active=result; $('#detail').hidden=false;
  $('#detailTitle').textContent=result.title;
  $('#detailMeta').textContent=`${result.id} · ${result.start} → ${result.end} · Rules ${result.rule_version}`;
  $('#export').href=`/api/investigations/${encodeURIComponent(result.id)}/report`;
  $('#findings').innerHTML=result.findings.length?result.findings.map(f=>`<article class="finding"><h3>${esc(f.title)} <span class="badge ${esc(f.severity)}">${esc(f.severity)}</span></h3><span class="confidence">${esc(f.service)} · ${esc(f.confidence)} confidence in causal hypothesis</span><p>${esc(f.explanation)}</p><div class="hypothesis"><h4>Working hypothesis</h4><p>${esc(f.hypothesis)}</p></div><h4>Supporting evidence</h4>${f.evidence_ids.map(id=>`<button class="citation" data-citation="${esc(id)}">${esc(id)} ↗</button>`).join('')}<h4>Recommended investigation steps</h4><ol>${f.next_steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ol></article>`).join(''):'<div class="empty">No configured thresholds were crossed. Review evidence coverage before drawing a health conclusion.</div>';
  $('#timeline').innerHTML=result.evidence.map(e=>`<div class="event"><time>${esc(new Date(e.timestamp).toISOString().slice(11,19))} UTC</time><div>${esc(e.summary)}<small>${esc(e.service)} · ${esc(e.kind)} · ${esc(e.id)}</small></div></div>`).join('');
  $('#limitations').innerHTML='<strong>ANALYSIS BOUNDARIES</strong><br>'+result.limitations.map(esc).join('<br>');
  $('#evidenceSearch').value=''; evidenceList(); tab('findings'); renderQueue();
}
async function run(body,path) {
  document.querySelectorAll('[data-scenario],#uploadButton').forEach(b=>b.disabled=true);
  notice('Validating records and correlating evidence…');
  try {const result=await api(path,body);await refresh();show(result);notice(`Investigation ready · ${result.evidence_count} unique records · ${result.findings.length} findings`);$('#detail').scrollIntoView({behavior:'smooth'});}
  catch(e){notice(e.message,true);}
  finally{document.querySelectorAll('[data-scenario],#uploadButton').forEach(b=>b.disabled=false);}
}
document.addEventListener('click',async event=>{
  const scenario=event.target.closest('[data-scenario]');if(scenario) return run({name:scenario.dataset.scenario},'/api/scenarios');
  const row=event.target.closest('[data-id]');if(row){try{show(await api('/api/investigations/'+encodeURIComponent(row.dataset.id)));}catch(e){notice(e.message,true);}}
  const t=event.target.closest('[data-tab]');if(t)tab(t.dataset.tab);
  const citation=event.target.closest('[data-citation]');if(citation){tab('evidence');$('#evidenceSearch').value='';evidenceList();const item=document.getElementById(citation.dataset.citation);if(item){item.open=true;item.scrollIntoView({behavior:'smooth'});}}
});
$('#search').addEventListener('input',renderQueue);
$('#evidenceSearch').addEventListener('input',evidenceList);
$('#uploadButton').addEventListener('click',()=>$('#upload').click());
$('#upload').addEventListener('change',async event=>{
  const file=event.target.files[0];if(!file)return;
  try{if(file.size>5*1024*1024)throw new Error('File exceeds the 5 MiB import limit.');const raw=await file.text();let records;if(raw.trim().startsWith('[')) records=JSON.parse(raw);else records=raw.split(/\r?\n/).filter(s=>s.trim()).map(s=>JSON.parse(s));await run(records,'/api/investigations');}catch(e){notice('Import failed: '+e.message,true);}finally{event.target.value='';}
});
refresh().then(()=>{if(investigations.length)return api('/api/investigations/'+investigations[0].id).then(show);}).catch(e=>notice('Could not connect to the local engine: '+e.message,true));
