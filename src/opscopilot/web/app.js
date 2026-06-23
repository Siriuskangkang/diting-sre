(function(){
'use strict';
/* === 谛听 DiTing 前端：调用 FastAPI 后端 (/api/*)，无假数据 === */
const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
const S={tab:'rag',searchMode:'hybrid',agentRunning:false};

/* ===== Tab 切换 ===== */
function switchTab(tab){
  S.tab=tab;
  $$('.nav-icon[data-tab]').forEach(e=>e.classList.toggle('active',e.dataset.tab===tab));
  $$('.view-panel').forEach(e=>e.classList.toggle('active',e.dataset.view===tab));
  if(tab==='kb') loadKB();
  if(tab==='incidents') loadIncidents();
}
$$('.nav-icon[data-tab]').forEach(e=>e.addEventListener('click',()=>switchTab(e.dataset.tab)));

/* ===== 顶栏时钟 ===== */
function tick(){
  const t=new Date().toLocaleTimeString('zh-CN',{hour12:false});
  const el=$('.topbar-clock'); if(el) el.textContent=t+' CST';
}
tick(); setInterval(tick,1000);

/* ===== 工具 ===== */
function h(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
async function api(path,opts){
  const r=await fetch(path,opts);
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||('HTTP '+r.status));}
  return r.json();
}

/* ===== RAG 问答 ===== */
const chatList=$('#chat-list'),chatInput=$('#chat-input'),sendBtn=$('#send-btn');
const modeChips=$$('.mode-chip');
modeChips.forEach(c=>c.addEventListener('click',function(){
  modeChips.forEach(m=>m.classList.remove('active'));
  this.classList.add('active');S.searchMode=this.dataset.mode;
}));

function appendMsg(role,content){
  const div=document.createElement('div');
  div.className='chat-msg '+(role==='user'?'user':'ai');
  const av=document.createElement('div');
  av.className='msg-avatar '+(role==='user'?'user-av':'ai-av');
  av.textContent=role==='user'?'U':'AI';
  const body=document.createElement('div');body.className='msg-body';
  body.textContent=content;
  div.appendChild(av);div.appendChild(body);
  chatList.appendChild(div);chatList.scrollTop=chatList.scrollHeight;
  return body;
}
function renderSources(body,sources){
  (sources||[]).forEach(s=>{
    const sc=document.createElement('div');sc.className='source-card';
    sc.innerHTML='<div class="source-file">'+h(s.file)+'</div>'+
      '<div class="source-snippet">'+h(s.snippet)+'</div>'+
      '<div class="source-bar"><div class="source-bar-fill" style="width:'+(s.score||80)+'%"></div></div>';
    body.appendChild(sc);
  });
  chatList.scrollTop=chatList.scrollHeight;
}

async function sendChat(){
  const txt=chatInput.value.trim();if(!txt)return;
  appendMsg('user',txt);
  chatInput.value='';chatInput.style.height='auto';
  sendBtn.disabled=true;
  const body=appendMsg('ai','正在检索知识库并生成回答…');
  const aiMsg=body.parentElement;aiMsg.classList.add('loading');
  try{
    const data=await api('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:txt,mode:S.searchMode})});
    aiMsg.classList.remove('loading');
    body.innerHTML=marked.parse(data.answer);
    renderSources(body,data.sources);
  }catch(e){
    aiMsg.classList.remove('loading');
    body.textContent='❌ 出错了：'+e.message;
  }
  sendBtn.disabled=false;
}
sendBtn.addEventListener('click',sendChat);
chatInput.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();}});
chatInput.addEventListener('input',function(){this.style.height='auto';this.style.height=Math.min(this.scrollHeight,120)+'px';});

/* ===== Agent 排障 ===== */
const startBtn=$('#start-btn'),resetBtn=$('#reset-btn'),reportCard=$('#report-card');
const nodeIds=['node-triage','node-supervisor','node-investigate','node-report'];
const conns=['#conn-1 .flow-line, #conn-1 .flow-arrow','#bidi-fwd, #bidi-fwd-arrow','#conn-3 .flow-line, #conn-3 .flow-arrow'];
let flowTimer=null;

function resetAgent(){
  if(flowTimer)clearTimeout(flowTimer);
  S.agentRunning=false;
  $$('.flow-node').forEach(n=>n.classList.remove('active','done'));
  $$('.flow-line,.flow-arrow').forEach(l=>l.classList.remove('active'));
  $('#timeline-list').innerHTML='<div style="color:var(--muted);font-size:13px;padding:20px 0;text-align:center">点击「开始排障」启动 Agent 工作流</div>';
  reportCard.style.display='none';reportCard.innerHTML='';
  startBtn.disabled=false;
}
function playFlow(){
  let i=0;
  function step(){
    nodeIds.forEach(n=>$('#'+n).classList.remove('active'));
    if(i>0)$('#'+nodeIds[i-1]).classList.add('done');
    if(i>0&&i-1<conns.length)$$(conns[i-1]).forEach(el=>el.classList.add('active'));
    $('#'+nodeIds[Math.min(i,nodeIds.length-1)]).classList.add('active');
    i++;
    if(S.agentRunning)flowTimer=setTimeout(step,900);
  }
  step();
}
function finishFlow(){
  if(flowTimer)clearTimeout(flowTimer);
  nodeIds.forEach(n=>{$('#'+n).classList.remove('active');$('#'+n).classList.add('done');});
}

async function startAgent(){
  if(S.agentRunning)return;
  const query=$('#trouble-input').value.trim();
  if(!query){$('#trouble-input').focus();return;}
  resetAgent();S.agentRunning=true;startBtn.disabled=true;
  $('#timeline-list').innerHTML='<div class="tl-item active"><div class="tl-time">运行中</div><div class="tl-result">Agent 正在 分诊 → 调工具取证 → 生成报告…</div></div>';
  playFlow();
  try{
    const data=await api('/api/agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query})});
    finishFlow();
    const tl=$('#timeline-list');
    if(data.evidence&&data.evidence.length){
      tl.innerHTML=data.evidence.map((e,idx)=>'<div class="tl-item done">'+
        '<div class="tl-time">证据 '+(idx+1)+'</div>'+
        '<span class="tl-tool">'+h(e.tool||'tool')+'</span>'+
        '<div class="tl-result">'+h(e.result)+'</div></div>').join('');
    }else{
      tl.innerHTML='<div class="tl-item done"><div class="tl-result">未收集到工具证据</div></div>';
    }
    tl.scrollTop=tl.scrollHeight;
    reportCard.style.display='block';
    let html='<div class="card-header"><span class="card-title">排障报告</span></div>';
    if(data.triage)html+='<div class="triage-box"><strong>分诊结论</strong>\n'+h(data.triage)+'</div>';
    html+='<div class="report-section">'+(window.marked?marked.parse(data.report||'(无报告)'):h(data.report||''))+'</div>';
    reportCard.innerHTML=html;
  }catch(e){
    finishFlow();
    $('#timeline-list').innerHTML='<div class="tl-item done"><div class="tl-result">❌ 排障失败：'+h(e.message)+'</div></div>';
  }
  S.agentRunning=false;startBtn.disabled=false;
}
startBtn.addEventListener('click',startAgent);
resetBtn.addEventListener('click',resetAgent);

/* ===== 知识库 ===== */
const uploadZone=$('#upload-zone'),fileInput=$('#file-input'),kbTable=$('#kb-table-body'),clearBtn=$('#clear-kb-btn');

async function loadKB(){
  try{
    const st=await api('/api/kb/status');
    $('#stat-chunks').textContent=st.chunks;
    const docs=await api('/api/kb/documents');
    $('#stat-docs').textContent=docs.total;
    renderKBTable(docs.documents);
  }catch(e){console.error('loadKB',e);}
}
function renderKBTable(docs){
  if(!docs||!docs.length){kbTable.innerHTML='<tr><td colspan="5" style="color:var(--muted);text-align:center;padding:20px">知识库为空</td></tr>';return;}
  kbTable.innerHTML=docs.map(d=>'<tr>'+
    '<td class="mono">'+h(d.file)+'</td>'+
    '<td class="mono">'+d.chunks+'</td>'+
    '<td><span class="kb-status"><span class="kb-dot ok"></span>就绪</span></td>'+
    '<td class="mono">-</td>'+
    '<td><button class="kb-del" data-file="'+h(d.file)+'">删除</button></td></tr>').join('');
  $$('.kb-del').forEach(b=>b.addEventListener('click',async function(){
    const f=this.dataset.file;
    if(!confirm('删除 '+f+' ？'))return;
    try{await api('/api/kb/document?file='+encodeURIComponent(f),{method:'DELETE'});loadKB();}
    catch(e){alert('删除失败：'+e.message);}
  }));
}
async function uploadFiles(fileList){
  if(!fileList||!fileList.length)return;
  const fd=new FormData();
  for(const f of fileList)fd.append('files',f);
  uploadZone.style.opacity='.5';
  try{
    const r=await api('/api/kb/upload',{method:'POST',body:fd});
    loadKB();
    let msg='✅ 入库 '+r.added+' 篇 → '+r.chunks+' 个 chunk（共 '+r.total+'）';
    if(r.skipped && r.skipped.length) msg+='\n⚠️ 解析失败/跳过: '+r.skipped.join(', ');
    alert(msg);
  }catch(e){alert('上传失败：'+e.message);}
  uploadZone.style.opacity='1';
}
uploadZone.addEventListener('click',()=>fileInput.click());
uploadZone.addEventListener('dragover',e=>{e.preventDefault();uploadZone.classList.add('drag-over');});
uploadZone.addEventListener('dragleave',()=>uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop',e=>{e.preventDefault();uploadZone.classList.remove('drag-over');uploadFiles(e.dataTransfer.files);});
fileInput.addEventListener('change',function(){uploadFiles(this.files);this.value='';});
clearBtn.addEventListener('click',async()=>{
  if(!confirm('确定清空整个知识库？不可恢复。'))return;
  try{await api('/api/kb',{method:'DELETE'});loadKB();alert('已清空');}catch(e){alert('失败：'+e.message);}
});

/* ===== 告警排障（事件流）===== */
const incidentsList=$('#incidents-list');

async function loadStats(){
  try{
    const s=await api('/api/stats');
    const el=$('#incidents-stats'); if(!el) return;
    el.innerHTML=[
      ['总告警', s.total_incidents],
      ['排障成功率', s.total_incidents?((s.success_rate*100).toFixed(0)+'%'):'-'],
      ['平均 MTTR', s.avg_mttr_seconds?Math.round(s.avg_mttr_seconds)+'s':'-'],
      ['🧬 自增长知识', (s.evolved_runbooks||0)+' 篇 / '+(s.auto_evolved_chunks||0)+' chunks'],
    ].map(x=>'<div class="stat-card"><div class="stat-value" style="font-size:20px">'+x[0]+'</div><div class="stat-label">'+x[1]+'</div></div>').join('');
  }catch(e){}
}
async function loadIncidents(){
  loadStats();
  try{
    const data=await api('/api/incidents');
    renderIncidents(data.incidents||[]);
  }catch(e){ incidentsList.innerHTML='<div class="card" style="color:var(--danger)">加载失败: '+h(e.message)+'</div>'; }
}
function renderActions(inc){
  const executed=inc.actions_status==='executed';
  const riskColor={high:'var(--danger)',medium:'var(--warn)',low:'var(--success)'};
  const items=(inc.pending_actions||[]).map((a,i)=>{
    const rc=riskColor[a.risk]||'var(--muted)';
    const res=(inc.actions_results&&inc.actions_results[i])?('<div class="tl-result">✓ '+h(inc.actions_results[i].result)+'</div>'):'';
    return '<div style="margin:6px 0;padding:8px 10px;background:var(--hover);border-radius:6px;border-left:3px solid '+rc+'">'+
      '<div style="font-size:12px;line-height:1.6"><span style="color:'+rc+';font-weight:700">['+(a.risk||'?').toUpperCase()+']</span> '+
      '<span class="mono" style="color:var(--info)">'+h(a.action_type||'action')+'</span> '+h(a.description||'')+'</div>'+res+'</div>';
  }).join('');
  const btn=executed?'<span class="tl-tool" style="color:var(--success);border-color:rgba(52,211,153,0.3);background:rgba(52,211,153,0.1)">✓ 已执行</span>':
    '<button class="btn btn-accent btn-sm" data-approve="'+inc.id+'">✓ 批准并执行修复</button>';
  return '<div class="report-section" style="margin-top:10px"><strong>🔧 可执行修复动作'+(executed?'':'（待审批）')+'：</strong>'+items+'<div style="margin-top:8px">'+btn+'</div></div>';
}
function renderIncidents(list){
  if(!list.length){ incidentsList.innerHTML='<div class="card" style="text-align:center;color:var(--muted);padding:48px">暂无告警事件<br><br>点「🔔 模拟告警触发排障」体验谛听自动排查闭环</div>'; return; }
  const sevColor={critical:'var(--danger)',warning:'var(--warn)',info:'var(--info)'};
  const statusMap={investigating:'排查中',resolved:'已完成',error:'出错'};
  incidentsList.innerHTML=list.map(inc=>{
    const sc=sevColor[inc.severity]||'var(--muted)';
    const time=new Date((inc.created_at||0)*1000).toLocaleTimeString('zh-CN',{hour12:false});
    return '<div class="card mb-16">'+
      '<div class="flex-between mb-12"><div class="flex-row" style="gap:10px">'+
        '<span style="color:'+sc+';font:600 11px var(--font-mono)">'+(inc.severity||'info').toUpperCase()+'</span>'+
        '<span class="card-title mono">'+h(inc.alertname||'未命名告警')+'</span>'+
        '<span style="color:var(--muted);font-size:12px">'+h(inc.service||'')+'</span>'+
      '</div><div class="flex-row" style="gap:8px">'+
        '<span class="tl-tool">'+(statusMap[inc.status]||inc.status)+'</span>'+
        (inc.evolved?'<span style="color:var(--accent);font:600 10px var(--font-mono);border:1px solid rgba(45,212,191,0.3);background:rgba(45,212,191,0.1);padding:2px 6px;border-radius:4px">🧬 已沉淀</span>':'')+
        '<span class="tl-time">'+time+'</span>'+
      '</div></div>'+
      '<div class="report-section"><strong>故障描述:</strong> '+h(inc.query||'')+'</div>'+
      (inc.report?'<div class="report-section"><strong>排查报告:</strong><br>'+(window.marked?marked.parse(inc.report):h(inc.report))+'</div>':'<div style="color:var(--accent);font-size:13px">⏳ 谛听排障进行中… 点「刷新」查看</div>')+
      ((inc.pending_actions&&inc.pending_actions.length)||inc.actions_status==='executed'?renderActions(inc):'')+
    '</div>';
  }).join('');
  $$('#incidents-list [data-approve]').forEach(b=>b.addEventListener('click',async function(){
    const id=this.dataset.approve;
    this.disabled=true; this.textContent='执行中…';
    try{ const r=await api('/api/incidents/'+id+'/approve',{method:'POST'}); alert('✅ 已审批执行 '+r.executed+' 个修复动作'); loadIncidents(); }
    catch(e){ alert('执行失败: '+e.message); this.disabled=false; this.textContent='✓ 批准并执行修复'; }
  }));
}
async function triggerMockAlert(){
  const btn=$('#mock-alert-btn'); if(btn) btn.disabled=true;
  const payload={version:"4",groupKey:"{}",status:"firing",alerts:[{
    status:"firing",
    labels:{alertname:"High5xxRate",service:"order-service",severity:"critical"},
    annotations:{summary:"order-service 5xx 错误率飙升至 5.6%",description:"订单服务 5xx 飙升，伴随 Pod CrashLoopBackOff 与 OOMKilled，疑似连接池耗尽"},
    fingerprint:"mock-"+Date.now()
  }]};
  try{
    await api('/api/alerts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    alert('✅ 已触发模拟告警，谛听正在后台排障（约 30–60s）。\n稍后点「刷新」查看结果。');
    loadIncidents();
    setTimeout(loadIncidents,60000);
  }catch(e){ alert('触发失败: '+e.message); }
  if(btn) btn.disabled=false;
}
const mockAlertBtn=$('#mock-alert-btn'),refreshIncidentsBtn=$('#refresh-incidents-btn');
if(mockAlertBtn) mockAlertBtn.addEventListener('click',triggerMockAlert);
if(refreshIncidentsBtn) refreshIncidentsBtn.addEventListener('click',loadIncidents);

/* ===== Init ===== */
loadKB();
})();
