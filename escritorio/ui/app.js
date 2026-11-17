const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = null;
let currentField = null;
let currentPage = 'workspace';
let toastTimer;
let requesting = false;
let previewRequest = 0;
let historySignature = '';
let historyText = '';
let addHistory = true;
let revisionDate = new Date().toLocaleDateString('en-CA');

async function api(action, payload = {}) {
  const response = await fetch('/api/' + action, {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Session': window.SESSION},
    body: JSON.stringify(payload)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'No se pudo completar la operación.');
  return result;
}
function toast(text, error = false) {
  $('toast').textContent = text;
  $('toast').className = 'toast' + (error ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.add('hidden'), error ? 11000 : 4500);
}
async function perform(action, payload = {}) {
  if (requesting) return;
  requesting = true;
  try {
    const result = await api(action, payload);
    await refresh();
    return result;
  } catch (error) {
    toast(error.message, true);
    throw error;
  } finally { requesting = false; }
}
async function refresh() {
  const response = await fetch('/api/state', {headers: {'X-Session': window.SESSION}});
  if (!response.ok) throw new Error('Se perdió la conexión con la aplicación. Vuelve a abrirla.');
  state = await response.json();
  render();
}
function render() {
  $('update-notice').classList.toggle('hidden', !!state.app_version && !state.restart_required);
  document.title='Materia '+(state.app_version || '· motor anterior');
  $('word-name').textContent = state.word || 'Arrastra tu Word o elige un archivo';
  $('pdf-name').textContent = state.pdfs.length ? state.pdfs.length + ' PDF · ' + state.pdfs.join(', ') : 'Fichas técnicas, certificados y hojas de seguridad';
  $('material-badge').classList.toggle('hidden', !state.sap);
  $('material-badge').textContent = state.sap + ' · Versión ' + state.version;
  $('demo-help').classList.toggle('hidden', !state.demo);
  $('demo-button').disabled = state.busy;
  $('analyze-button').disabled = state.busy || !state.word || !state.pdfs.length || !state.sections.length;
  const errors = state.notes.filter(n => n.type === 'error');
  $('analyze-button').innerHTML = (errors.length ? 'Reintentar pendientes' : 'Analizar documentos') + ' <span>→</span>';
  if (state.no_keys) {
    if (currentPage === 'workspace' && !window._firstRunPrompted) {
      window._firstRunPrompted = true;
      navigate('settings');
    }
    if ($('service-banner')) $('service-banner').classList.remove('hidden');
    if ($('service-config')) $('service-config').open = true;
    $('analyze-button').disabled = true;
    $('analyze-button').title = 'Configura al menos una clave API en Configuración para comenzar';
  } else {
    if ($('service-banner')) $('service-banner').classList.add('hidden');
  }
  renderKeysList();
  $('scope-button').disabled = state.busy;
  document.querySelectorAll('#scope-menu input').forEach(input => input.checked = state.sections.includes(input.value));
  $('progress-panel').classList.toggle('hidden', !state.busy);
  $('analysis-progress').max = Math.max(1, state.progress.total);
  $('analysis-progress').value = state.progress.finished;
  $('progress-message').textContent = state.progress.message || 'Analizando documentación';
  $('preview-button').disabled = state.busy || !state.word;
  $('export-button').disabled = state.busy || !state.approved_count;
  $('manual-button').disabled = state.busy || !state.word;
  $('empty-manual').disabled = state.busy || !state.word;
  $('change-count').textContent = state.fields.filter(f => f.proposals.length || f.approved != null).length;
  $('note-count').textContent = state.notes.length;
  $('approved-label').textContent = state.approved_count + ' aprobados';
  $('export-title').textContent = state.approved_count ? state.approved_count + ' cambio(s) aprobado(s) para la versión ' + (state.version + 1) : 'Tu expediente, listo para documentar.';
  $('footer-state').textContent = state.busy ? 'Análisis en curso' : errors.length ? errors.length + ' PDF requieren atención' : state.word ? 'Materia prima ' + state.sap : 'Preparado para comenzar';
  $('commercial-attention').classList.toggle('hidden', !state.commercial_attention);
  renderRows();
  $('notes-view').innerHTML = state.notes.length ? state.notes.map(n => '<div class="note ' + esc(n.type) + '"><strong>' + esc(n.file) + '</strong>' + esc(n.text) + '</div>').join('') : '<div class="empty-state"><h3>Sin observaciones por el momento</h3><p>El resultado de cada documento aparecerá aquí.</p></div>';
}
function renderRows() {
  if (!state) return;
  const query = $('search').value.toLocaleLowerCase();
  const rows = state.fields.filter(f => (!query || (f.label + ' ' + f.before).toLocaleLowerCase().includes(query)) && (!$('proposals-only').checked || f.proposals.length || f.approved != null))
    .sort((a,b) => (b.kind==='manufacturer') - (a.kind==='manufacturer'));
  renderMakerFirst();
  $('empty-state').classList.toggle('hidden', rows.length > 0);
  $('table-container').classList.toggle('hidden', !rows.length);
  $('field-rows').innerHTML = rows.map(f => {
    const groups = ProposalGroups.group(f);
    const makers = f.kind==='range_add' ? ProposalGroups.rangeMakers(f) : [];
    const conflict = f.kind==='range_add' ? makers.some(m=>m.variants.length>1) : groups.length > 1;
    const status = f.approved != null ? 'approved' : conflict ? 'conflict' : f.proposals.length ? 'pending' : 'manual';
    const label = {approved:'Aprobado',conflict:f.kind==='manufacturer'?'Fabricantes por revisar':'Opciones para elegir',pending:makers.length>1?makers.length+' fabricantes':groups[0]?.members.length>1?'Fuentes agrupadas':'Por revisar',manual:'Sin propuesta'}[status];
    const allVerified = f.proposals.length && f.proposals.every(p=>p.verified);
    const after = f.approved ?? (f.proposals.length ? '' : '—');
    const provenance = f.kind==='manufacturer' ? groups.map(g=>makerCard(f,g)).join('') : groups.map((g,gi)=> {
      const title=f.kind==='manufacturer'?'Fabricante: '+g.maker:g.detail;
      const subtitle=f.kind==='range_add'?'Fabricante: '+g.maker:'';
      const sourceLinks=g.members.filter((p,i,a)=>a.findIndex(q=>q.pdf===p.pdf&&q.page===p.page)===i).map(p=>'<button class="source-link" data-field="'+esc(f.id)+'" data-proposal="'+p.index+'"><span>'+esc(p.pdf)+'</span><strong>Pág. '+esc(p.page)+' ↗</strong></button>').join('');
      const variants=g.variants.map((v,vi)=>'<div class="proposal-variant">'+(f.kind==='manufacturer'?'<small class="variant-origin">'+v.sources.map(s=>esc(s.pdf)+' · p. '+esc(s.page)).join('<br>')+'</small><pre>'+esc(v.value)+'</pre>':'')+'<button class="secondary small proposal-pick" data-field="'+esc(f.id)+'" data-proposal="'+v.index+'">'+(f.kind==='manufacturer'?'Elegir estos datos':'Elegir este valor')+'</button></div>').join('');
      const fixed=g.members.some(p=>p.original)?' · corregido en la segunda revisión':'';
      return '<div class="proposal-card"><strong>'+esc(title)+'</strong>'+(subtitle?'<small>'+esc(subtitle)+'</small>':'')+'<span class="proposal-meta">'+g.members.length+' respaldo(s)'+(g.members.length>1?' · redacciones equivalentes':'')+(g.members.every(p=>p.verified)?' · ✓ verificado por IA':'')+fixed+'</span>'+variants+sourceLinks+'</div>';
    }).join('');
    const combined = f.kind==='range_add' && f.proposals.length ? '<div class="cell-preview"><b>ASÍ QUEDARÁ LA CELDA RANGO</b>'+esc(ProposalGroups.rangeResult(f.cell,existingNumbers(),state.manufacturer_numbers||{},makers.map(m=>'Fabricante: '+m.maker+' | '+m.variants[0].value).join('\n')).text)+'</div>' : '';
    return '<tr><td>' + esc(f.label) + '<small>Sección ' + esc(f.section) + '</small></td><td><div class="value">' + esc(beforeText(f) || '—') + '</div></td><td><div class="value">' + esc(after) + '</div>' + combined + provenance + '</td><td><span class="status ' + status + '">' + label + '</span></td><td><button class="row-edit" aria-label="Revisar campo" data-id="' + f.id + '">↗</button></td></tr>';
  }).join('');
  document.querySelectorAll('.proposal-pick').forEach(button=>button.onclick=()=>editField(button.dataset.field,Number(button.dataset.proposal)));
  document.querySelectorAll('.row-edit').forEach(button => button.onclick = () => editField(button.dataset.id));
  // La página citada se abre dentro del detalle, con la evidencia resaltada.
  document.querySelectorAll('.source-link').forEach(button => button.onclick = () => editField(button.dataset.field, null, Number(button.dataset.proposal)));
}
function renderMakerFirst(){
  const box=$('maker-first'), f=state.fields.find(x=>x.kind==='manufacturer');
  const groups=f?ProposalGroups.group(f):[];
  if(!f||(!groups.length&&f.approved==null)){box.classList.add('hidden');return;}
  const numbers=state.manufacturer_numbers||{};
  if(f.approved!=null){
    const names=Array.from(f.approved.matchAll(/^fabricante\s*:\s*(.+)$/gim),m=>m[1].trim());
    box.innerHTML='<strong>Fabricantes nuevos aprobados</strong><p>'+names.map(n=>'('+esc(numbers[ProposalGroups.entityKey(n)]??'?')+') '+esc(n)).join(' · ')+'. Ahora revisa los rangos de A: cada fabricante aporta su propia línea en la celda RANGO.</p><button class="secondary small" id="maker-first-open">Cambiar fabricantes</button>';
  } else {
    const next=Math.max(0,...existingNumbers())+1;
    box.innerHTML='<strong>Primero, los fabricantes: se detectaron '+groups.length+' fabricante(s) nuevo(s)</strong><p>'+groups.map((g,i)=>'<span>('+(next+i)+') '+esc(g.maker)+'</span>').join(' · ')+'. Apruébalos antes que los rangos: el orden de aprobación define su número en B, y los rangos de A se asignan a ese número.</p><button class="primary small" id="maker-first-open">Revisar fabricantes nuevos</button>';
  }
  box.classList.remove('hidden');
  $('maker-first-open').onclick=()=>editField(f.id);
}
let rangeState = [];
function renderRangeChoices(f){
  const numbers=state.manufacturer_numbers||{};
  const approvedLines=(f.approved||'').split(/\n/).filter(Boolean);
  rangeState=ProposalGroups.rangeMakers(f).map(m=>{
    const previous=approvedLines.find(l=>ProposalGroups.entityKey(ProposalGroups.describe(f,{value:l}).maker)===m.key);
    const number=numbers[m.key];
    return {...m,number,include:f.approved!=null?!!previous:number!=null,choice:0,text:previous?ProposalGroups.describe(f,{value:previous}).detail:m.variants[0].value};
  });
  $('proposal-choices').innerHTML='<h3>Un rango por fabricante</h3><p class="helper">Cada fabricante nuevo aporta su propia línea (n) en la celda RANGO; puedes incluir varios a la vez. Solo eliges cuando un mismo fabricante tiene redacciones distintas. El valor se puede corregir antes de aprobar.</p>'+rangeState.map((m,gi)=>'<fieldset class="proposal-choice-group maker-group'+(m.include?'':' excluded')+'"><legend><label><input type="checkbox" class="range-include" data-group="'+gi+'"'+(m.include?' checked':'')+'> '+(m.number!=null?'('+m.number+') ':'')+esc(m.maker)+'</label></legend>'+(m.number==null?'<p class="maker-pending">Este fabricante aún no está aprobado en B. Apruébalo primero en «Agregar fabricante y su bloque comercial» para asignarle su número.</p>':'')+'<div class="maker-rows">'+(m.variants.length>1?m.variants.map((v,vi)=>'<label class="alt"><input type="radio" name="rv-'+gi+'" class="range-variant" data-group="'+gi+'" value="'+vi+'"'+(vi===0?' checked':'')+'><span>'+esc(v.value)+'<br>'+sourceJumps(v.sources)+'</span></label>').join(''):'<div>'+sourceJumps(m.variants[0].sources)+'</div>')+'<label class="field-label">Valor para este fabricante<input class="range-text" data-group="'+gi+'" value="'+esc(m.text)+'"></label></div></fieldset>').join('');
  document.querySelectorAll('.range-include').forEach(i=>i.onchange=()=>{const m=rangeState[Number(i.dataset.group)];m.include=i.checked;i.closest('fieldset').classList.toggle('excluded',!m.include);composeRanges();});
  document.querySelectorAll('.range-variant').forEach(i=>i.onchange=()=>{const gi=Number(i.dataset.group),m=rangeState[gi];m.text=m.variants[Number(i.value)].value;document.querySelector('.range-text[data-group="'+gi+'"]').value=m.text;composeRanges();showEvidence(m.variants[Number(i.value)].sources[0].index);});
  document.querySelectorAll('.range-text').forEach(i=>i.oninput=()=>{rangeState[Number(i.dataset.group)].text=i.value;composeRanges();});
  document.querySelectorAll('.evidence-jump').forEach(b=>b.onclick=e=>{e.preventDefault();showEvidence(Number(b.dataset.proposal));});
}
function composeRanges(){
  $('editor-value').value=rangeState.filter(m=>m.include&&m.text.trim()).map(m=>'Fabricante: '+m.maker+' | '+m.text.trim()).join('\n');
  updateRangeResult();
}
const existingNumbers = () => (state.manufacturers||[]).map(m=>m.number);
function beforeText(f){
  if (f.kind==='range_add') return f.cell || '';
  if (f.kind==='range') return f.cell || ('('+f.manufacturer_number+') '+f.before);
  return f.before;
}
function makerCard(f,g){
  const rows=ProposalGroups.mergeManufacturer(g);
  const conflicts=rows.filter(r=>r.options.length>1).length;
  const docs=g.members.filter((p,i,a)=>a.findIndex(q=>q.pdf===p.pdf)===i).length;
  const sourceLinks=g.members.filter((p,i,a)=>a.findIndex(q=>q.pdf===p.pdf&&q.page===p.page)===i).map(p=>'<button class="source-link" data-field="'+esc(f.id)+'" data-proposal="'+p.index+'"><span>'+esc(p.pdf)+'</span><strong>Pág. '+esc(p.page)+' ↗</strong></button>').join('');
  return '<div class="proposal-card"><strong>Fabricante: '+esc(g.maker)+'</strong><span class="proposal-meta">'+docs+' documento(s)'+(conflicts?' · '+conflicts+' dato(s) con valores distintos':docs>1?' · datos combinados':'')+'</span><div class="cell-preview">'+esc(ProposalGroups.composeBlock(rows))+'</div><button class="secondary small proposal-pick" data-field="'+esc(f.id)+'" data-proposal="'+g.members[0].index+'">'+(conflicts?'Elegir datos':'Revisar e incluir')+'</button>'+sourceLinks+'</div>';
}
function showTab(tab) {
  $('changes-view').classList.toggle('hidden', tab !== 'changes');
  $('notes-view').classList.toggle('hidden', tab !== 'notes');
  $('changes-tab').classList.toggle('active', tab === 'changes');
  $('notes-tab').classList.toggle('active', tab === 'notes');
}
function manualMode() {
  if (!state.word) return toast('Carga primero la especificación vigente.', true);
  $('proposals-only').checked = false;
  $('search').value = '';
  showTab('changes');
  renderRows();
  $('search').focus();
  $('search').scrollIntoView({behavior:'smooth', block:'center'});
}
async function navigate(page) {
  currentPage = page;
  document.querySelectorAll('.page').forEach(el => el.classList.add('hidden'));
  $(page + '-page').classList.remove('hidden');
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.page === page));
  $('breadcrumb').textContent = {workspace:'Especificaciones técnicas', settings:'Configuración', catalog:'Proveedores y fabricantes', history:'Historial de análisis'}[page];
  if (page === 'history') loadHistory();
  if (page === 'settings') {
    $('settings-folder').value = state.settings.salida || '';
    $('settings-applicant').value = state.settings.solicitante || '';
    $('settings-area').value = state.settings.area || '';
    $('settings-template').value = state.settings.plantilla || 'AS-REG-018 · Plantilla incluida';
    $('settings-renderer').value = state.settings.renderizador || '';
    updateProviderUI();
    renderKeysList();
  }
  if (page === 'catalog') {
    try {
      const result = await api('catalog');
      $('catalog-content').innerHTML = result.entities.length ? result.entities.map(([role,name]) => '<div class="note"><strong>' + esc(role.toUpperCase()) + '</strong>' + esc(name) + '</div>').join('') : '<div class="empty-state"><div class="empty-symbol">▤</div><h3>El catálogo crece con tu trabajo</h3><p>Al exportar un expediente, sus proveedores y fabricantes se incorporan aquí.<br>Carga un Word para consultar su materia prima.</p></div>';
    } catch (e) { toast(e.message,true); }
  }
}
let historyItems = [];
const formatDate = value => {try {return new Date(value).toLocaleString('es-PE',{dateStyle:'medium',timeStyle:'short'});} catch {return value;}};
async function loadHistory() {
  $('history-content').innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
  try {
    const result = await api('history_list');
    historyItems = result.items;
    renderHistory(result.current);
  } catch (e) { $('history-content').innerHTML = ''; toast(e.message, true); }
}
function renderHistory(current = state?.history_id) {
  const query = $('history-search').value.toLocaleLowerCase();
  const items = historyItems.filter(i => !query || [i.sap, i.word, ...i.pdfs].join(' ').toLocaleLowerCase().includes(query));
  $('history-content').innerHTML = items.length ? items.map(i => '<article class="history-item' + (i.id === current ? ' current' : '') + '"><div><h3>' + esc(i.sap || 'Sin código') + ' · Versión ' + esc(i.version ?? '—') + (i.id === current ? ' · abierto ahora' : '') + '</h3><p>' + esc(i.word) + ' · ' + i.pdfs.length + ' PDF: ' + esc(i.pdfs.join(', ')) + '</p><p>Analizado ' + esc(formatDate(i.creado)) + (i.actualizado !== i.creado ? ' · última revisión ' + esc(formatDate(i.actualizado)) : '') + '</p><div class="history-badges"><span>' + esc(i.secciones.length === 4 ? 'Todas las secciones' : i.secciones.map(s => s === 'ID' ? 'Identificación' : s).join(', ')) + '</span><span>' + i.propuestas + ' campo(s) con propuestas</span><span class="' + (i.aprobados ? 'ok' : '') + '">' + i.aprobados + ' aprobado(s)</span>' + (i.errores ? '<span class="err">' + i.errores + ' PDF con error</span>' : '') + (i.exportado ? '<span class="ok">Exportado</span>' : '') + '</div></div><div class="history-actions"><button class="primary small history-open" data-id="' + esc(i.id) + '">Reabrir</button><button class="text-button history-delete" data-id="' + esc(i.id) + '">Eliminar</button></div></article>').join('')
    : '<div class="empty-state"><div class="empty-symbol">◷</div><h3>' + (historyItems.length ? 'Sin resultados' : 'Todavía no hay análisis guardados') + '</h3><p>Cada vez que analices documentos, el resultado quedará aquí para reabrirlo sin volver a consultar a la IA.</p></div>';
  document.querySelectorAll('.history-open').forEach(b => b.onclick = async () => {
    if (state.busy) return toast('Espera a que termine el análisis en curso.', true);
    if (state.word && !state.history_id && state.approved_count && !confirm('Tienes aprobaciones sin guardar en el historial. ¿Reabrir de todos modos?')) return;
    try {await perform('history_open', {id: b.dataset.id}); await navigate('workspace'); showTab('changes'); toast('Análisis reabierto con sus propuestas y aprobaciones.');} catch {}
  });
  document.querySelectorAll('.history-delete').forEach(b => b.onclick = async () => {
    if (!confirm('¿Eliminar este análisis del historial? Se borran sus copias locales; los expedientes exportados no se tocan.')) return;
    try {await perform('history_delete', {id: b.dataset.id}); await loadHistory();} catch {}
  });
}
$('history-search').oninput = () => renderHistory();
function readFile(file) {
  return new Promise((resolve,reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({name:file.name,data:String(reader.result).split(',')[1]});
    reader.onerror = () => reject(new Error('No se pudo leer ' + file.name));
    reader.readAsDataURL(file);
  });
}
async function upload(kind, files) {
  if (!files.length || state.busy) return;
  if (Array.from(files).some(f => f.size > 20000000)) return toast('Cada archivo debe pesar como máximo 20 MB.',true);
  toast('Cargando y validando documentos…');
  try {
    await perform('upload',{kind,files:await Promise.all(Array.from(files).map(readFile))});
    toast(kind === 'template' ? 'Plantilla actualizada.' : 'Documentos cargados.');
    if (kind === 'template') navigate('settings');
  } catch {}
}
let makerState = [];
let evidenceRequest = 0;
function sourceJumps(sources){
  return sources.map(p=>'<button type="button" class="evidence-jump" data-proposal="'+p.index+'">'+esc(p.pdf)+' · p. '+esc(p.page)+'</button>').join('');
}
function renderMakerChoices(f, groups){
  const approvedKeys = f.approved ? Array.from(f.approved.matchAll(/^fabricante\s*:\s*(.+)$/gim),m=>ProposalGroups.entityKey(m[1])) : null;
  makerState = groups.map(g=>({maker:g.maker,rows:ProposalGroups.mergeManufacturer(g),choice:{}}));
  makerState.forEach(m=>m.include = approvedKeys ? approvedKeys.includes(ProposalGroups.entityKey(m.maker)) : true);
  $('proposal-choices').innerHTML='<h3>Fabricantes encontrados</h3><p class="helper">Cada fabricante reúne los datos de todos sus documentos. Marca los que se incorporan como bloques nuevos en B; se numeran en el orden mostrado a partir del siguiente número libre. Razones sociales distintas no se fusionan. Solo debes elegir cuando dos documentos dan valores distintos para el mismo dato.</p>'+makerState.map((m,gi)=>'<fieldset class="proposal-choice-group maker-group'+(m.include?'':' excluded')+'" data-group="'+gi+'"><legend><label><input type="checkbox" class="maker-include" data-group="'+gi+'"'+(m.include?' checked':'')+'> Incorporar '+esc(m.maker)+'</label></legend><div class="maker-rows">'+m.rows.map((r,ri)=>'<div class="maker-row"><span>'+esc(r.role)+'</span><div>'+(r.options.length>1?'<span class="conflict-tag">Valores distintos · elige uno</span>'+r.options.map((o,oi)=>'<label class="alt"><input type="radio" name="mk-'+gi+'-'+ri+'" class="maker-option" data-group="'+gi+'" data-row="'+ri+'" value="'+oi+'"'+(oi===0?' checked':'')+'><span>'+esc(o.value)+'<br>'+sourceJumps(o.sources)+'</span></label>').join(''):'<div class="single">'+esc(r.options[0].value)+'</div>'+sourceJumps(r.options[0].sources))+'</div></div>').join('')+'</div></fieldset>').join('');
  document.querySelectorAll('.maker-include').forEach(input=>input.onchange=()=>{const m=makerState[Number(input.dataset.group)];m.include=input.checked;input.closest('fieldset').classList.toggle('excluded',!m.include);composeMakers();});
  document.querySelectorAll('.maker-option').forEach(input=>input.onchange=()=>{const m=makerState[Number(input.dataset.group)];m.choice[m.rows[Number(input.dataset.row)].key]=Number(input.value);composeMakers();});
  document.querySelectorAll('.evidence-jump').forEach(button=>button.onclick=e=>{e.preventDefault();showEvidence(Number(button.dataset.proposal));});
}
function composeMakers(){
  $('editor-value').value=makerState.filter(m=>m.include).map(m=>ProposalGroups.composeBlock(m.rows,m.choice)).join('\n\n');
}
function showEvidence(index){
  $('source-select').value=String(index);
  updateEvidence(false);
}
function updateRangeResult(){
  const f=currentField, box=$('range-result');
  if(!f||!['range','range_add'].includes(f.kind)){box.classList.add('hidden');return;}
  let text, hint;
  if(f.kind==='range_add'){
    const r=ProposalGroups.rangeResult(f.cell,existingNumbers(),state.manufacturer_numbers||{},$('editor-value').value);
    text=r.text;
    hint=r.pending.length?'(nuevo): el número se asigna al aprobar el bloque de '+r.pending.join(', ')+' en «Agregar fabricante y su bloque comercial». Los demás fabricantes conservan su valor.':'Cada (n) corresponde al fabricante numerado en B. Los demás fabricantes conservan su valor.';
  } else {
    const value=$('editor-value').value.replace(/^\s*\(\d+\)\s*/,'').trim();
    text=ProposalGroups.rangeEntries(f.cell).map(e=>(e.n!=null?'('+e.n+') ':'')+(e.n===f.manufacturer_number?value:e.text)).join('\n');
    hint='Solo cambia el rango del fabricante ('+f.manufacturer_number+'); los demás se conservan.';
  }
  box.innerHTML='<strong>Así quedará la celda RANGO</strong><pre>'+esc(text||'—')+'</pre><small>'+esc(hint)+'</small>';
  box.classList.remove('hidden');
}
async function loadEvidencePage(p){
  const request=++evidenceRequest, frame=$('evidence-page-frame');
  if(!p){$('evidence-page').classList.add('hidden');return;}
  $('evidence-page').classList.remove('hidden');
  $('evidence-page-info').textContent=p.pdf+' · página '+p.page;
  frame.innerHTML='<div class="preview-message" role="status"><span class="spinner"></span><p>Cargando la página citada…</p></div>';
  try{
    const r=await api('pdf_page',{name:p.pdf,page:p.page,evidence:p.evidence||'',value:p.value||''});
    if(request!==evidenceRequest)return;
    $('evidence-page-info').innerHTML=esc(p.pdf+' · página '+r.page+' de '+r.pages)+(r.found?' · <strong>cita resaltada'+(r.method==='ocr'?' (OCR local)':'')+'</strong>':' · <span class="evidence-warning">no se ubicó el texto citado; revisa la página visualmente</span>');
    frame.innerHTML='<img alt="Página '+esc(r.page)+' de '+esc(p.pdf)+'" src="'+r.image+'">';
    const img=frame.querySelector('img');
    if(r.focus!=null)img.onload=()=>{frame.scrollTop=Math.max(0,img.offsetHeight*r.focus-90);};
  }catch(e){
    if(request!==evidenceRequest)return;
    frame.innerHTML='<div class="preview-message" role="alert"><p>'+esc(e.message)+'</p></div>';
  }
}
function editField(id, selectedIndex = null, evidenceIndex = null) {
  currentField = state.fields.find(f => f.id === id);
  const f = currentField;
  if (!f || state.busy) return;
  $('editor-section').textContent = 'SECCIÓN ' + f.section;
  $('editor-title').textContent = f.label;
  $('editor-before').textContent = beforeText(f) || 'Sin contenido';
  $('editor-before-label').textContent = ['range','range_add'].includes(f.kind) ? 'Celda RANGO vigente' : 'Valor vigente';
  $('editor-layout').classList.toggle('no-evidence', !f.proposals.length);
  $('evidence-page').classList.add('hidden');
  $('evidence-page-frame').classList.remove('zoomed');
  $('evidence-zoom').textContent='Ampliar';
  evidenceRequest++;
  $('editor-error').textContent = '';
  $('add-source-range').classList.add('hidden');
  $('approve-button').textContent = f.kind === 'manufacturer' ? 'Aprobar fabricantes marcados ✓' : 'Aprobar este valor ✓';
  const groups=ProposalGroups.group(f);
  const conflict = groups.length > 1 || (f.kind==='manufacturer' && groups.some(g=>g.variants.length>1));
  $('editor-value').value = f.approved ?? (!conflict ? f.proposals[0]?.value : null) ?? f.before;
  $('source-select').innerHTML = (conflict ? '<option value="">Elige una propuesta o fuente para comparar</option>' : '') + f.proposals.map((p,i) => '<option value="' + i + '">' + esc((ProposalGroups.describe(f,p).maker || ProposalGroups.describe(f,p).detail).slice(0,65))+' · '+esc(p.pdf) + ' · página ' + p.page + '</option>').join('');
  $('evidence-panel').classList.toggle('hidden', !f.proposals.length);
  $('manual-note').classList.toggle('hidden', !!f.proposals.length);
  if (f.kind === 'range_add') {
    $('manual-note').classList.remove('hidden');
    $('manual-note').textContent=f.proposals.length?'Marca los fabricantes cuyo rango se incorpora. Los demás fabricantes de la celda conservan su valor.':'Escribe una línea por fabricante: Fabricante: nombre completo | rango. El fabricante debe estar aprobado en B.';
  } else if (f.kind === 'range') {
    $('manual-note').classList.remove('hidden');
    $('manual-note').textContent='Este rango corresponde al fabricante ('+f.manufacturer_number+'). Se conservarán los rangos de los demás fabricantes.';
  } else if (f.kind === 'add' || f.kind === 'additional') {
    $('manual-note').classList.remove('hidden');
    $('manual-note').textContent = 'Para agregar una fila, separa sus columnas con “ | ”. Ejemplo: Parámetro | Rango | Técnica.';
  } else if (f.kind === 'manufacturer') {
    $('manual-note').classList.remove('hidden');
    $('manual-note').textContent = 'El texto se arma con los fabricantes marcados y puedes corregirlo antes de aprobar. Cada bloque comienza con Fabricante: nombre, con una línea por dato (Proveedor, Nombre Comercial, Tiempo de Vida útil, Almacenamiento). Para parámetros sin técnica interna: Parámetro adicional: Nombre | Rango | Referencia.';
  } else $('manual-note').textContent = 'Escribe el valor completo que debe quedar en el documento.';
  if (f.kind === 'manufacturer' && groups.length) {
    renderMakerChoices(f, groups);
    if (f.approved == null) composeMakers();
    updateEvidence(false);
    if (f.proposals.length) showEvidence(evidenceIndex ?? selectedIndex ?? groups[0].members[0].index);
    updateRangeResult();
    $('editor-dialog').showModal();
    return;
  }
  makerState = [];
  $('editor-value-box').classList.toggle('hidden', f.kind === 'range_add' && f.proposals.length > 0);
  if (f.kind === 'range_add' && f.proposals.length) {
    renderRangeChoices(f);
    if (f.approved == null) composeRanges(); else $('editor-value').value = f.approved;
    updateEvidence(false);
    showEvidence(evidenceIndex ?? selectedIndex ?? rangeState[0].variants[0].sources[0].index);
    updateRangeResult();
    $('editor-dialog').showModal();
    return;
  }
  $('proposal-choices').innerHTML = groups.length ? '<h3>Elige la propuesta que debe quedar</h3><p class="helper">Las redacciones equivalentes comparten grupo. Las diferencias de contenido se mantienen para tu revisión. Puedes editar el valor antes de aprobar.</p>'+groups.map((g,gi)=>'<fieldset class="proposal-choice-group"><legend>'+esc(g.maker||'Opción '+(gi+1))+'</legend>'+g.variants.map(v=>'<label class="proposal-radio"><input type="radio" name="proposal-choice" value="'+v.index+'"><span><strong>'+esc(f.kind==='manufacturer'?'Datos comerciales · '+v.sources[0].pdf:ProposalGroups.describe(f,{value:v.value}).detail)+'</strong><small>'+v.sources.map(p=>esc(p.pdf)+' · p. '+esc(p.page)).join('<br>')+'</small></span></label>').join('')+'</fieldset>').join('') : '';
  document.querySelectorAll('input[name="proposal-choice"]').forEach(input=>input.onchange=()=>selectProposal(Number(input.value)));
  updateEvidence(false);
  if(selectedIndex != null) selectProposal(selectedIndex);
  else if(evidenceIndex != null) showEvidence(evidenceIndex);
  else if(f.approved == null && !conflict && f.proposals.length) selectProposal(0);
  else if(f.proposals.length) showEvidence(0);
  updateRangeResult();
  $('editor-dialog').showModal();
}
function selectProposal(index) {
  $('source-select').value=String(index);
  updateEvidence(true);
  const variant=ProposalGroups.group(currentField).flatMap(g=>g.variants).find(v=>v.sources.some(p=>p.index===index));
  document.querySelectorAll('input[name="proposal-choice"]').forEach(input=>input.checked=Number(input.value)===(variant?.index??index));
}
function updateEvidence(updateValue) {
  const index = $('source-select').value;
  const proposal = index === '' ? null : currentField.proposals[Number(index)];
  $('evidence-text').textContent = proposal?.evidence || 'Selecciona una de las propuestas y revisa su respaldo.';
  $('open-source').disabled = !proposal;
  if (updateValue && proposal) $('editor-value').value = proposal.value;
  loadEvidencePage(proposal);
  updateRangeResult();
}
async function pickFolder(target) {
  try {
    const result = await perform('folder');
    if (result?.path) {
      $(target).value = result.path;
      toast('Carpeta autorizada para guardar expedientes.');
    }
  } catch {}
}
function openExport() {
  $('export-applicant').value = state.settings.solicitante || '';
  $('export-area').value = state.settings.area || '';
  $('export-folder').value = state.settings.salida || '';
  const now = new Date();
  $('export-date').value = revisionDate;
  $('export-preview').innerHTML = '<strong>' + esc(state.sap) + ' · Versión ' + (state.version + 1) + '</strong>' + state.approved_count + ' cambio(s) aprobado(s)<br>Word actualizado · Solicitud Excel · ' + state.pdfs.length + ' PDF · Registro de cambios';
  const errors = state.notes.some(n => n.type === 'error');
  $('partial-warning').classList.toggle('hidden', !errors);
  $('partial-warning').textContent = 'Hay PDF pendientes de análisis. Se exportarán los valores que hayas aprobado y se registrarán los documentos pendientes.';
  $('export-error').textContent = '';
  $('export-dialog').showModal();
}
document.querySelectorAll('.nav-item').forEach(button => button.onclick = () => navigate(button.dataset.page));
$('demo-button').onclick = async () => {try {await perform('demo');showTab('changes');toast('Ejemplo cargado. Pulsa Analizar documentos o usa Cambio manual.');}catch{}};
$('word-input').onchange = async e => {await upload('word',e.target.files);e.target.value='';};
$('pdf-input').onchange = async e => {await upload('pdfs',e.target.files);e.target.value='';};
$('template-input').onchange = e => upload('template',e.target.files);
$('template-button').onclick = () => $('template-input').click();
for (const [id,kind] of [['word-drop','word'],['pdf-drop','pdfs']]) {
  $(id).ondragover = e => {e.preventDefault();$(id).classList.add('dragging');};
  $(id).ondragleave = () => $(id).classList.remove('dragging');
  $(id).ondrop = e => {e.preventDefault();$(id).classList.remove('dragging');upload(kind,e.dataTransfer.files);};
  $(id).onkeydown = e => {if(e.key==='Enter'||e.key===' '){e.preventDefault();$(kind==='word'?'word-input':'pdf-input').click();}};
}
$('scope-button').onclick = () => $('scope-menu').classList.toggle('hidden');
$('scope-save').onclick = async () => {try {await perform('sections',{sections:Array.from(document.querySelectorAll('#scope-menu input:checked')).map(i=>i.value)});$('scope-menu').classList.add('hidden');}catch{}};
$('analyze-button').onclick = async () => {try {await perform('analyze');showTab('changes');}catch{}};
$('cancel-button').onclick = async () => {try{await api('cancel');toast('El análisis se detendrá al finalizar las solicitudes en curso.');}catch(e){toast(e.message,true);}};
$('changes-tab').onclick = () => showTab('changes');
$('notes-tab').onclick = () => showTab('notes');
$('manual-button').onclick = manualMode;
$('empty-manual').onclick = manualMode;
$('search').oninput = renderRows;
$('proposals-only').onchange = renderRows;
$('source-select').onchange = () => updateEvidence(!['manufacturer','range_add'].includes(currentField.kind));
$('add-source-range').onclick=()=>{
 const index=$('source-select').value;
 const proposal=index===''?null:currentField.proposals[Number(index)];
 if(!proposal)return toast('Selecciona una fuente.',true);
 const value=proposal.value.trim(),current=$('editor-value').value.trim();
 const key=ProposalGroups.entityKey(ProposalGroups.describe(currentField,proposal).maker);
 const lines=current.split(/\n/).filter(Boolean);
 if(lines.some(line=>ProposalGroups.entityKey(ProposalGroups.describe(currentField,{value:line}).maker)===key))return toast('Ya hay un rango para ese fabricante. Elige o edita su valor para evitar duplicarlo.',true);
 $('editor-value').value=current?current+'\n'+value:value;
 toast('Rango añadido para su fabricante.');
};
$('open-source').onclick = async () => {const p=currentField.proposals[Number($('source-select').value)];if(p)try{await api('open_pdf',{name:p.pdf});}catch(e){toast(e.message,true);}};
$('editor-value').oninput = updateRangeResult;
$('evidence-zoom').onclick = () => {const zoomed=$('evidence-page-frame').classList.toggle('zoomed');$('evidence-zoom').textContent=zoomed?'Ajustar':'Ampliar';};
$('discard-button').onclick = async () => {
  try {await perform('discard',{id:currentField.id});$('editor-dialog').close();toast('Cambio descartado.');}catch{}
};
$('approve-button').onclick = async () => {
  try {
    if (currentField.kind==='manufacturer' && !$('editor-value').value.trim()) throw new Error('Marca al menos un fabricante para incorporar o escribe su bloque.');
    await perform('approve',{id:currentField.id,value:$('editor-value').value});
    $('editor-dialog').close();toast('Cambio aprobado para la exportación.');
  } catch(e) {$('editor-error').textContent=e.message;}
};
$('settings-pick-folder').onclick = () => pickFolder('settings-folder');
$('export-pick-folder').onclick = () => pickFolder('export-folder');
$('save-settings').onclick = async () => {try{await perform('settings',{salida:$('settings-folder').value,solicitante:$('settings-applicant').value,area:$('settings-area').value,renderizador:$('settings-renderer').value});toast('Preferencias guardadas.');}catch{}};
const PROVIDER_MODELS = {
  gemini: [
    {value: 'gemini-3.5-flash', label: 'gemini-3.5-flash (Recomendado / Gratis)'},
    {value: 'gemini-2.5-flash', label: 'gemini-2.5-flash'},
    {value: 'gemini-2.0-flash', label: 'gemini-2.0-flash'},
    {value: 'gemini-2.0-flash-lite', label: 'gemini-2.0-flash-lite'}
  ],
  groq: [
    {value: 'openai/gpt-oss-120b', label: 'openai/gpt-oss-120b (Recomendado)'},
    {value: 'llama-3.3-70b-versatile', label: 'llama-3.3-70b-versatile'},
    {value: 'llama-3.1-8b-instant', label: 'llama-3.1-8b-instant'}
  ]
};

function updateProviderUI() {
  const provider = $('service-provider')?.value || 'gemini';
  const select = $('model-select');
  const free = $('model-free');
  if (!select || !free) return;
  if (provider === 'openrouter') {
    select.classList.add('hidden');
    free.classList.remove('hidden');
    free.value = state?.settings?.openrouter_model || 'google/gemini-2.5-flash';
  } else {
    select.classList.remove('hidden');
    free.classList.add('hidden');
    const models = PROVIDER_MODELS[provider] || [];
    select.innerHTML = models.map(m => `<option value="${esc(m.value)}">${esc(m.label)}</option>`).join('');
    const current = provider === 'gemini' ? (state?.settings?.modelo || 'gemini-3.5-flash') : (state?.settings?.groq_model || 'openai/gpt-oss-120b');
    if (models.some(m => m.value === current)) {
      select.value = current;
    }
  }
}

function renderKeysList() {
  const container = $('keys-list');
  if (!container || !state?.keys_count) return;
  const counts = state.keys_count;
  const items = [
    {id: 'gemini', name: 'Google Gemini', count: counts.gemini || 0},
    {id: 'groq', name: 'Groq', count: counts.groq || 0},
    {id: 'openrouter', name: 'OpenRouter', count: counts.openrouter || 0}
  ];
  container.innerHTML = '<div style="margin-top:10px;font-size:13px;display:flex;gap:10px;flex-wrap:wrap;">' +
    items.map(it => `<span style="background:${it.count ? '#e8f5e9':'#f5f5f5'};color:${it.count ? '#2e7d32':'#757575'};padding:4px 8px;border-radius:6px;font-weight:500;">${esc(it.name)}: ${it.count} clave(s)</span>`).join('') +
    '</div>';
}

if ($('service-provider')) {
  $('service-provider').onchange = () => updateProviderUI();
}

if ($('add-key')) {
  $('add-key').onclick = async () => {
    try {
      const provider = $('service-provider').value;
      const keyVal = $('service-key').value.trim();
      const modelVal = provider === 'openrouter' ? $('model-free').value.trim() : $('model-select').value;

      if (keyVal) {
        await api('credentials', {[provider]: keyVal});
      }

      if (provider === 'gemini') {
        await perform('settings', {modelo: modelVal});
      } else if (provider === 'openrouter') {
        await perform('settings', {openrouter_model: modelVal});
      } else if (provider === 'groq') {
        await perform('settings', {groq_model: modelVal});
      }

      $('service-key').value = '';
      toast(keyVal ? 'Clave y modelo guardados correctamente.' : 'Modelo guardado.');
      await poll();
    } catch(e) {
      toast(e.message, true);
    }
  };
}
async function ensureHistory() {
  const signature = JSON.stringify([state.word, state.fields.filter(f=>f.approved!=null).map(f=>[f.id,f.approved])]);
  if (signature !== historySignature) {
    historyText = (await api('history')).text;
    historySignature = signature;
  }
}
function previewLoading() {
  $('word-preview').setAttribute('aria-busy','true');
  $('word-preview').innerHTML = '<div class="preview-message" role="status"><span class="spinner"></span><h3>Preparando vista previa…</h3><p>Estamos aplicando los cambios aprobados a una copia del Word.</p></div>';
}
async function updatePreview() {
  const request = ++previewRequest;
  historyText = $('history-text').value;
  addHistory = $('history-enabled').checked;
  revisionDate = $('preview-date').value;
  $('preview-error').textContent = '';
  previewLoading();
  $('refresh-preview').disabled = true;
  try {
    const result = await api('preview', {fecha:revisionDate,add_history:addHistory,history_text:historyText,mode:$('preview-mode').value});
    if (request !== previewRequest) return;
    const notice = !state.approved_count ? 'Documento vigente: todavía no has aprobado cambios. Las propuestas no se aplican hasta que las apruebes.' : addHistory && !historyText.trim() ? 'Vista de los cambios aprobados. Completa la revisión histórica o desactiva su registro antes de exportar.' : '';
    $('word-preview').innerHTML = (notice ? '<div class="preview-notice" role="status">'+esc(notice)+'</div>' : '') + (result.pages ? result.pages.map((src,i)=>'<figure class="document-page"><figcaption>Página '+(i+1)+' · '+esc(result.renderer)+'</figcaption><img src="'+src+'" alt="Página '+(i+1)+' del Word"></figure>').join('') : result.html);
  } catch(e) {
    if (request !== previewRequest) return;
    $('preview-error').textContent=e.message;
    $('word-preview').innerHTML='<div class="preview-message" role="alert"><h3>No se pudo generar la vista previa</h3><p>'+esc(e.message)+'</p><p>Corrige los datos y pulsa Actualizar vista previa para reintentar.</p></div>';
  } finally {
    if (request === previewRequest) {$('word-preview').setAttribute('aria-busy','false');$('refresh-preview').disabled=false;}
  }
}
$('preview-button').onclick = async () => {
  $('preview-error').textContent='';
  $('preview-date').value=revisionDate;
  $('preview-dialog').showModal();
  previewLoading();
  try {
    await ensureHistory();
    $('history-text').value=historyText;
    $('history-enabled').checked=addHistory;
    await updatePreview();
  } catch(e) {
    $('preview-error').textContent=e.message;
    $('word-preview').setAttribute('aria-busy','false');
    $('word-preview').innerHTML='<div class="preview-message" role="alert"><h3>No se pudo preparar el documento</h3><p>'+esc(e.message)+'</p><p>Pulsa Actualizar vista previa para reintentar.</p></div>';
  }
};
$('close-preview').onclick=()=>{historyText=$('history-text').value;addHistory=$('history-enabled').checked;revisionDate=$('preview-date').value;$('preview-dialog').close();};
$('refresh-preview').onclick=updatePreview;
$('history-enabled').onchange=updatePreview;
$('regenerate-history').onclick=async()=>{historySignature='';await ensureHistory();$('history-text').value=historyText;await updatePreview();};
$('export-button').onclick = async () => {try {await ensureHistory();openExport();}catch(e){toast(e.message,true);}};
$('create-export').onclick = async () => {
  const button=$('create-export');
  try {
    if (!$('export-applicant').value.trim() || !$('export-area').value.trim() || !$('export-date').value || !$('export-folder').value) throw new Error('Completa solicitante, área, fecha y carpeta de destino.');
    button.disabled=true;button.textContent='Creando expediente…';
    const result=await perform('export',{salida:$('export-folder').value,solicitante:$('export-applicant').value,area:$('export-area').value,fecha:$('export-date').value,add_history:addHistory,history_text:historyText});
    $('export-dialog').close();$('success-path').textContent=result.path;$('success-dialog').showModal();
  }catch(e){$('export-error').textContent=e.message;}finally{button.disabled=false;button.textContent='Crear expediente ↗';}
};
$('open-export').onclick = async () => {try{await api('open_export');}catch(e){toast(e.message,true);}};
$('close-success').onclick = () => $('success-dialog').close();
async function poll() {
  try {
    const wasBusy=state?.busy;
    await refresh();
    if(wasBusy&&!state.busy){
      const failed=state.notes.some(n=>n.type==='error');
      toast(failed?'Algunos documentos requieren atención. Puedes reintentar o editar manualmente. Detalle técnico: Monitor técnico (Ctrl/⌘ + Shift + L).':'Análisis completado. Revisa las propuestas.',failed);
      if(failed&&!state.fields.some(f=>f.proposals.length))showTab('notes');
    }
  }catch(e){toast(e.message,true);}
  setTimeout(poll,state?.busy?1000:4000);
}
poll();

$('load-techniques').onclick=async()=>{try{const r=await api('techniques');$('techniques-list').innerHTML=r.items.map(t=>'<details><summary>'+esc(t.codigo+' · '+t.archivo)+'</summary><pre class="technique-detail">'+esc(t.texto)+'</pre></details>').join('');}catch(e){toast(e.message,true);}};

$('commercial-notes').onclick=()=>showTab('notes');
$('commercial-manual').onclick=()=>{const f=state.fields.find(f=>f.kind==='manufacturer');if(f)editField(f.id);};

$('preview-mode').onchange=updatePreview;
let connectionTimer;
async function refreshConnection(force=false) {
  clearTimeout(connectionTimer);
  try {
    const result=await api('connectivity',{force});
    $('connectivity-indicator').className='connection '+result.state;
    $('connection-label').textContent={online:'Con Internet',offline:'Sin conexión verificada',checking:'Comprobando conexión…'}[result.state];
    connectionTimer=setTimeout(refreshConnection,result.state==='checking'?1500:20000);
  } catch(e) {
    $('connectivity-indicator').className='connection offline';
    $('connection-label').textContent='No se pudo comprobar la conexión';
    connectionTimer=setTimeout(refreshConnection,20000);
  }
}
$('connectivity-indicator').onclick=()=>refreshConnection(true);
window.addEventListener('online',()=>refreshConnection(true));
window.addEventListener('offline',()=>{$('connectivity-indicator').className='connection offline';$('connection-label').textContent='Sin conexión';});
refreshConnection();

/* Monitor técnico: eventos en tiempo real del análisis, llamadas a la IA y errores. */
let monitorAfter = 0, monitorTimer = null, monitorEvents = [];
function monitorRender(){
  const debug=$('monitor-debug').checked, onlyIssues=$('monitor-errors').checked;
  const rows=monitorEvents.filter(e=>(debug||e.level!=='debug')&&(!onlyIssues||['warn','error'].includes(e.level)));
  const log=$('monitor-log'), atBottom=log.scrollHeight-log.scrollTop-log.clientHeight<40;
  log.innerHTML=rows.map(e=>'<div class="monitor-row '+esc(e.level)+'"><span class="t">'+esc(e.time)+'</span> <span class="s">['+esc(e.source)+']</span> <span class="m">'+esc(e.message)+'</span>'+(e.detail?'<details'+(e.level==='error'?' open':'')+'><summary>detalle técnico</summary><pre>'+esc(e.detail)+'</pre></details>':'')+'</div>').join('')||'<div class="monitor-row">Sin eventos todavía. Inicia un análisis para ver las llamadas al servicio y sus respuestas.</div>';
  if(atBottom)log.scrollTop=log.scrollHeight;
}
async function monitorPoll(){
  clearTimeout(monitorTimer);
  if($('monitor').classList.contains('hidden'))return;
  try{
    const r=await api('logs',{after:monitorAfter});
    if(r.events.length){monitorEvents=monitorEvents.concat(r.events).slice(-3000);monitorAfter=r.events[r.events.length-1].seq;monitorRender();}
    $('monitor-status').textContent=(r.busy?'Análisis en curso · '+(r.progress.message||'')+' ('+r.progress.finished+'/'+r.progress.total+')':'En espera')+(r.file?' · registro: '+r.file:'');
  }catch(e){$('monitor-status').textContent='No se pudo leer el registro: '+e.message;}
  monitorTimer=setTimeout(monitorPoll,1000);
}
function toggleMonitor(open=$('monitor').classList.contains('hidden')){
  $('monitor').classList.toggle('hidden',!open);
  try{localStorage.setItem('materia-monitor',open?'1':'');}catch{}
  if(open){monitorRender();monitorPoll();}
}
$('monitor-open').onclick=()=>toggleMonitor(true);
$('monitor-close').onclick=()=>toggleMonitor(false);
$('monitor-debug').onchange=monitorRender;
$('monitor-errors').onchange=monitorRender;
$('monitor-clear').onclick=()=>{monitorEvents=[];monitorRender();};
$('monitor-folder').onclick=async()=>{try{await api('open_log');}catch(e){toast(e.message,true);}};
$('monitor-copy').onclick=async()=>{
  const text=monitorEvents.map(e=>e.time+' '+e.level.toUpperCase()+' ['+e.source+'] '+e.message+(e.detail?'\n    '+e.detail.replace(/\n/g,'\n    '):'')).join('\n');
  try{await navigator.clipboard.writeText(text);toast('Registro copiado.');}catch{toast('No se pudo copiar; usa Abrir carpeta del registro.',true);}
};
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.shiftKey&&e.key.toLowerCase()==='l'){e.preventDefault();toggleMonitor();}});
try{if(localStorage.getItem('materia-monitor'))toggleMonitor(true);}catch{}
