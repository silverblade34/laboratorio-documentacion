const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = null;
let currentField = null;
let currentPage = 'workspace';
let toastTimer;
let previewRequest = 0;
let historySignature = '';
let historyText = '';
let addHistory = true;
let revisionDate = new Date().toLocaleDateString('en-CA');

// Acciones que el usuario espera ver terminar (no las consultas periódicas de fondo).
const BACKGROUND = new Set(['logs', 'connectivity', 'keys_health', 'gemini_models', 'openrouter_models']);
let pendingRequests = 0, loadingTimer = null;
function setLoading(delta) {
  pendingRequests = Math.max(0, pendingRequests + delta);
  clearTimeout(loadingTimer);
  if (pendingRequests) loadingTimer = setTimeout(() => document.body.classList.add('working'), 350);
  else document.body.classList.remove('working');
}
async function api(action, payload = {}) {
  const tracked = !BACKGROUND.has(action);
  if (tracked) setLoading(1);
  try {
    const response = await fetch('/api/' + action, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-Session': window.SESSION},
      body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'No se pudo completar la operación.');
    return result;
  } finally { if (tracked) setLoading(-1); }
}
function toast(text, error = false) {
  $('toast').textContent = text;
  $('toast').className = 'toast' + (error ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.add('hidden'), error ? 11000 : 4500);
}
// Las acciones se encadenan: un clic durante otra acción espera su turno en lugar de perderse.
let actionQueue = Promise.resolve();
function perform(action, payload = {}) {
  const run = async () => {
    try {
      const result = await api(action, payload);
      await refresh();
      return result;
    } catch (error) {
      toast(error.message, true);
      throw error;
    }
  };
  const result = actionQueue.then(run, run);
  actionQueue = result.catch(() => {});
  return result;
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
  // El ejemplo preparado es opcional en la interfaz.
  if ($('demo-help')) $('demo-help').classList.toggle('hidden', !state.demo);
  if ($('demo-button')) $('demo-button').disabled = state.busy;
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
  $('scope-button').disabled = state.busy;
  document.querySelectorAll('#scope-menu input').forEach(input => input.checked = state.sections.includes(input.value));
  $('progress-panel').classList.toggle('hidden', !state.busy);
  $('analysis-progress').max = Math.max(1, state.progress.total);
  $('analysis-progress').value = state.progress.finished;
  $('progress-message').textContent = state.progress.message || 'Analizando documentación';
  $('preview-button').disabled = state.busy || !state.word;
  renderAnalysisResult(errors);
  $('export-button').disabled = state.busy || !state.approved_count;
  $('manual-button').disabled = state.busy || !state.word;
  $('empty-manual').disabled = state.busy || !state.word;
  $('change-count').textContent = state.fields.filter(f => f.proposals.length || f.approved != null).length;
  if ($('advanced-count')) $('advanced-count').textContent = '· ' + $('change-count').textContent + ' campo(s) · ' + state.notes.length + ' observación(es)';
  $('note-count').textContent = state.notes.length;
  $('approved-label').textContent = state.approved_count + ' aprobados';
  $('export-title').textContent = state.approved_count ? state.approved_count + ' cambio(s) aprobado(s) para la versión ' + (state.version + 1) : 'Tu expediente, listo para documentar.';
  $('footer-state').textContent = state.busy ? 'Análisis en curso' : errors.length ? errors.length + ' PDF requieren atención' : state.word ? 'Materia prima ' + state.sap : 'Preparado para comenzar';
  $('commercial-attention').classList.toggle('hidden', !state.commercial_attention);
  renderRows();
  renderReview();
  $('notes-view').innerHTML = state.notes.length ? state.notes.map(n => '<div class="note ' + esc(n.type) + '"><strong>' + esc(n.file) + '</strong>' + esc(n.text) + '</div>').join('') : '<div class="empty-state"><h3>Sin observaciones por el momento</h3><p>El resultado de cada documento aparecerá aquí.</p></div>';
}
function renderAnalysisResult(errors) {
  const hasResults = state.fields.some(f => f.proposals.length || f.approved != null);
  const analyzed = state.notes.some(n => n.type === 'success');
  $('export-bar').classList.toggle('hidden', state.busy || !hasResults);
  $('advanced-review').classList.toggle('hidden', state.busy || !(hasResults || state.notes.length));
  const box = $('analysis-result');
  if (state.busy || !errors.length) { box.classList.add('hidden'); return; }
  const failedAll = !analyzed;
  box.className = 'analysis-result ' + (failedAll ? 'failed' : 'partial');
  box.innerHTML = '<strong>' + (failedAll ? 'No se pudo analizar ningún PDF' : errors.length + ' PDF no se pudieron analizar') + '</strong>'
    + '<ul>' + errors.map(n => '<li><b>' + esc(n.file) + '</b>' + esc(n.text) + '</li>').join('') + '</ul>'
    + '<p>Suele deberse a claves saturadas o a un modelo sobrecargado. Revisa el estado de las claves o elige otro modelo y reintenta.</p>'
    + '<div><button class="primary small" id="result-retry">Reintentar</button> <button class="secondary small" id="result-keys">Ver estado de las claves</button></div>';
  $('result-retry').onclick = () => $('analyze-button').click();
  $('result-keys').onclick = showKeys;
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
    const status = f.approved != null ? 'approved' : f.rejected ? 'manual' : conflict ? 'conflict' : f.proposals.length ? 'pending' : 'manual';
    const label = f.rejected && f.approved == null ? 'Quitado' : {approved:'Aprobado',conflict:f.kind==='manufacturer'?'Fabricantes por revisar':'Opciones para elegir',pending:makers.length>1?makers.length+' fabricantes':groups[0]?.members.length>1?'Fuentes agrupadas':'Por revisar',manual:'Sin propuesta'}[status];
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
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.page === (page === 'review' ? 'workspace' : page)));
  $('breadcrumb').textContent = {workspace:'Especificaciones técnicas', review:'Revisión en el documento', settings:'Configuración', catalog:'Proveedores y fabricantes', history:'Historial de análisis'}[page];
  document.body.classList.toggle('reviewing', page === 'review');
  if (page === 'review') renderReview();
  if (page === 'history') loadHistory();
  if (page === 'settings') loadKeysHealth();
  if (page === 'settings') {
    $('settings-folder').value = state.settings.salida || '';
    $('settings-applicant').value = state.settings.solicitante || '';
    $('settings-area').value = state.settings.area || '';
    $('settings-template').value = state.settings.plantilla || 'AS-REG-018 · Plantilla incluida';
    $('settings-renderer').value = state.settings.renderizador || '';
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
    try {await perform('history_open', {id: b.dataset.id}); showTab('changes'); openReview(); toast('Análisis reabierto con sus propuestas y aprobaciones.');} catch {}
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
if ($('demo-button')) $('demo-button').onclick = async () => {try {await perform('demo');showTab('changes');toast('Ejemplo cargado. Pulsa Analizar documentos o usa Cambio manual.');}catch{}};
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
/* Vista de revisión en el documento: el Word se muestra como si se aprobaran todos los cambios
   incluidos; a la izquierda, cada cambio con su color para marcarlo conforme o quitarlo. */
const PALETTE_SIZE = 10;
let reviewFilter = 'all';
let activeChange = null;
let previewSignature = '';
let previewTimer = null;
let previewSkipped = {};
let historyEdited = false;
/* ---- Fabricantes y proveedores detectados: se deciden primero; los rangos de A dependen de ellos ---- */
const ROLE_KEYS = [['fabricante', 'Fabricante'], ['proveedor', 'Proveedor'], ['nombre comercial', 'Nombre Comercial'], ['tiempo de vida util', 'Tiempo de Vida útil'], ['almacenamiento', 'Almacenamiento']];
const foldText = v => String(v ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const GENERIC_WORDS = new Set(['co', 'ltd', 'limited', 'inc', 'llc', 'corp', 'corporation', 'sac', 'srl', 'eirl', 'gmbh', 'pvt', 'plc', 'spa', 'company', 'the', 'del', 'and', 'materials', 'material', 'technology', 'technologies', 'chemical', 'chemicals', 'industry', 'industries', 'industrial', 'trade', 'trading', 'group', 'international', 'pharma', 'chem', 'peru', 'quimica', 'quimicos', 'new']);
const nameTokens = n => foldText(n).split(/[^a-z0-9]+/).filter(t => t.length >= 3 && !GENERIC_WORDS.has(t));
const cleanValue = v => String(v ?? '').replace(/^\s*:\s*/, '').trim();
let makerChoices = {makers: {}};
let makerDirty = false;
let makerSaveTimer = null;
// Mismo fabricante con otro nombre (TINCI ↔ Guangzhou Tinci Materials Technology Co., Ltd.).
function matchExisting(name) {
  const tokens = nameTokens(name);
  if (!tokens.length) return null;
  return (state.manufacturers || []).find(m => {
    const t = nameTokens(m.name);
    return t.length && (t.every(x => tokens.includes(x)) || tokens.every(x => t.includes(x)));
  }) || null;
}
const makerField = () => state?.fields.find(f => f.kind === 'manufacturer');
function existingField(number, role) {
  return state.fields.find(f => f.section === 'B' && f.kind === 'text' && f.manufacturer_number === number && foldText(f.label.split(' · ')[0]).trim() === role);
}
function syncMakerChoices() {
  // Solo se adopta la copia del servidor si no es más antigua que la local (evita que un refresco pise un cambio).
  const server = state?.maker_choices || {};
  if (makerDirty || (server.rev || 0) < (makerChoices.rev || 0)) return;
  makerChoices = JSON.parse(JSON.stringify(server));
  makerChoices.makers = makerChoices.makers || {};
}
function makerEntries() {
  const f = makerField();
  if (!f || !f.proposals.length) return [];
  return ProposalGroups.group(f).map(g => {
    const key = ProposalGroups.entityKey(g.maker);
    const rows = ProposalGroups.mergeManufacturer(g);
    const detected = {};
    rows.forEach(r => { if (!r.key.startsWith('pa:')) detected[r.key] = r.options.map(o => o.value); });
    const extra = rows.filter(r => r.key.startsWith('pa:')).map(r => r.role + ': ' + r.options[0].value);
    const match = matchExisting(g.maker);
    const saved = makerChoices.makers[key] || {};
    const choice = {include: true, existing: match ? match.number : null, supplierMode: 'add', ...saved,
      values: {...Object.fromEntries(ROLE_KEYS.map(([k]) => [k, detected[k]?.[0] || ''])), ...(saved.values || {})},
      update: {...(saved.update || {})}};
    const roles = [];
    g.members.forEach(p => (p.roles || []).forEach(r => {
      if (!roles.some(x => x.rol === r.rol && ProposalGroups.entityKey(x.nombre) === ProposalGroups.entityKey(r.nombre))) roles.push(r);
    }));
    return {key, maker: g.maker, detected, extra, choice, roles, suggested: match, sources: g.members};
  });
}
function makersConfirmed() {
  const f = makerField();
  return !!makerChoices.confirmed || !!(f && f.approved != null);
}
// Resultado de la selección: bloques nuevos en B, cambios en bloques existentes y fabricantes incluidos.
function makerPlan() {
  const plan = {value: '', derived: {}, makers: {}, warnings: {}};
  const blocks = [];
  makerEntries().forEach(e => {
    const c = e.choice, v = c.values;
    const existing = c.existing != null ? (state.manufacturers || []).find(m => m.number === c.existing) : null;
    plan.makers[e.key] = c.include ? {existing: existing ? existing.number : null, name: existing ? existing.name : (v.fabricante || e.maker).trim()} : null;
    if (!c.include) return;
    if (!existing) {
      blocks.push(ROLE_KEYS.filter(([k]) => (v[k] || '').trim()).map(([k, label]) => label + ': ' + v[k].trim()).concat(e.extra).join('\n'));
      return;
    }
    ROLE_KEYS.slice(1).forEach(([k]) => {
      const value = (v[k] || '').trim();
      if (!value) return;
      const field = existingField(existing.number, k);
      if (!field) {
        if (k === 'proveedor') plan.warnings[e.key] = 'El bloque (' + existing.number + ') no tiene fila de Proveedor en el Word; agrégala manualmente.';
        return;
      }
      const current = cleanValue(field.before);
      let next;
      if (k === 'proveedor') {
        if (current.split('/').some(x => ProposalGroups.entityKey(x) === ProposalGroups.entityKey(value))) return;
        next = c.supplierMode === 'add' && current ? current + ' / ' + value : value;
      } else {
        if (!c.update[k] || ProposalGroups.entityKey(current) === ProposalGroups.entityKey(value)) return;
        next = value;
      }
      plan.derived[field.id] = ': ' + next;
    });
  });
  plan.value = blocks.join('\n\n');
  return plan;
}
// Líneas de rango por fabricante, según la selección: se quitan las de fabricantes no incluidos.
function planRangeLines(f, plan) {
  const seen = new Set();
  return ProposalGroups.rangeMakers(f).flatMap(m => {
    let line = {maker: m.maker, value: m.variants[0].value, isNew: false};
    if (m.key in plan.makers) {
      const target = plan.makers[m.key];
      if (!target) return [];
      line = {...line, maker: target.name, isNew: target.existing == null};
    }
    // Dos fabricantes detectados que apuntan al mismo bloque del Word aportan un solo rango (el primero).
    const key = ProposalGroups.entityKey(line.maker);
    if (seen.has(key)) return [];
    seen.add(key);
    return [line];
  });
}
function saveMakerChoices(rerender = true) {
  makerDirty = true;
  makerChoices.rev = Date.now();
  clearTimeout(makerSaveTimer);
  makerSaveTimer = setTimeout(async () => {
    try { await api('maker_choices', {choices: makerChoices}); } catch (e) { toast(e.message, true); }
    makerDirty = false;
  }, 500);
  if (rerender) { reviewSignature = ''; renderReview(); } else schedulePreview();
}
function updateChoice(key, change) {
  const entry = makerEntries().find(e => e.key === key);
  if (!entry) return;
  makerChoices.makers[key] = {...entry.choice, ...change, values: {...entry.choice.values, ...(change.values || {})}, update: {...entry.choice.update, ...(change.update || {})}};
}
async function confirmMakers() {
  const f = makerField(), plan = makerPlan();
  const ids = Object.keys(plan.derived);
  try {
    if (plan.value) await api('approve', {id: f.id, value: plan.value});
    else await api('reject', {id: f.id});
    for (const id of ids) await api('approve', {id, value: plan.derived[id]});
    makerChoices.confirmed = true; makerChoices.derivedIds = ids; makerChoices.rev = Date.now();
    clearTimeout(makerSaveTimer);
    await api('maker_choices', {choices: makerChoices});
    makerDirty = false;
    await refresh();
    toast(Object.values(plan.makers).some(Boolean) ? 'Fabricantes confirmados. Revisa ahora los rangos de la sección A.' : 'Ningún fabricante se incorpora; sus cambios de la sección A se quitaron.');
    return true;
  } catch (e) { toast(e.message, true); await refresh(); return false; }
}
async function unconfirmMakers() {
  const f = makerField();
  // Los rangos aprobados dependen de la selección: vuelven a quedar por revisar.
  const ranges = state.fields.filter(x => x.kind === 'range_add' && x.approved != null).map(x => x.id);
  await api('unapprove', {ids: [f.id, ...(makerChoices.derivedIds || []), ...ranges]});
  makerChoices.confirmed = false; makerChoices.derivedIds = []; makerChoices.rev = Date.now();
  await api('maker_choices', {choices: makerChoices});
  makerDirty = false;
  await refresh();
}
const existingName = n => (state.manufacturers || []).find(m => m.number === n)?.name || '';
function makerEditor(f) {
  const entries = makerEntries(), plan = makerPlan(), locked = makersConfirmed();
  const next = Math.max(0, ...existingNumbers());
  let counter = 0;
  return '<div class="maker-editor">' + entries.map(e => {
    const c = e.choice, k = esc(e.key), dis = locked ? ' disabled' : '';
    const newNumber = c.include && c.existing == null ? next + (++counter) : null;
    const chips = e.roles.map(r => '<span class="role-chip" title="' + esc(r.motivo || '') + '"><b>' + esc(r.rol) + '</b> ' + esc(r.nombre) + ' <small>' + esc([r.pais, r.fuente === 'Google' ? 'verificado en Google' : r.fuente === 'IA' ? 'validado por IA' : 'reglas'].filter(Boolean).join(' · ')) + '</small></span>').join('');
    const fields = ROLE_KEYS.map(([role, label]) => {
      if (role === 'fabricante' && c.existing != null) return '';
      const options = e.detected[role] || [];
      const current = c.existing != null ? existingField(c.existing, role) : null;
      const list = options.length > 1 ? '<datalist id="dl-' + k + '-' + role.replace(/\s/g, '') + '">' + options.map(o => '<option value="' + esc(o) + '">').join('') + '</datalist>' : '';
      let extra = '';
      if (c.existing != null && current) {
        extra = '<small class="mk-current">Actual: ' + esc(cleanValue(current.before) || '—') + '</small>';
        if (role === 'proveedor') extra += '<span class="mk-inline"><label><input type="radio" name="sm-' + k + '" class="mk-supplier" data-key="' + k + '" value="add"' + (c.supplierMode !== 'replace' ? ' checked' : '') + dis + '> Agregar como otro proveedor</label><label><input type="radio" name="sm-' + k + '" class="mk-supplier" data-key="' + k + '" value="replace"' + (c.supplierMode === 'replace' ? ' checked' : '') + dis + '> Reemplazar</label></span>';
        else extra += '<label class="mk-inline"><input type="checkbox" class="mk-update" data-key="' + k + '" data-role="' + role + '"' + (c.update[role] ? ' checked' : '') + dis + '> Actualizar este dato</label>';
      }
      return '<label class="mk-field"><span>' + label + (options.length > 1 ? ' <em>' + options.length + ' valores detectados</em>' : '') + '</span><input class="mk-value" data-key="' + k + '" data-role="' + role + '" value="' + esc(c.values[role] || '') + '"' + (list ? ' list="dl-' + k + '-' + role.replace(/\s/g, '') + '"' : '') + dis + '>' + list + extra + '</label>';
    }).join('');
    return '<div class="maker-edit' + (c.include ? '' : ' excluded') + '">'
      + '<label class="mk-head"><input type="checkbox" class="mk-include" data-key="' + k + '"' + (c.include ? ' checked' : '') + dis + '><span>' + esc(e.maker) + '</span></label>'
      + (chips ? '<div class="role-chips">' + chips + '</div>' : '')
      + (c.include ? (c.existing != null && existingName(c.existing)
          ? '<p class="mk-note">Ya está en el Word como (' + c.existing + ') ' + esc(existingName(c.existing)) + ': no se crea otro bloque, solo se actualizan sus datos (por ejemplo, el proveedor). ' + (locked ? '' : '<button type="button" class="text-button mk-as-new" data-key="' + k + '">Es otro fabricante</button>') + '</p>'
          : '<p class="mk-note">Se agregará como fabricante (' + newNumber + ').' + (e.suggested && !locked ? ' <button type="button" class="text-button mk-as-existing" data-key="' + k + '">Es el (' + e.suggested.number + ') ' + esc(e.suggested.name) + ' del Word</button>' : '') + '</p>')
        + '<div class="mk-fields">' + fields + '</div>'
        + (plan.warnings[e.key] ? '<p class="review-hint warn">' + esc(plan.warnings[e.key]) + '</p>' : '')
        : '<p class="review-hint">No se incorpora. Sus cambios en la sección A se quitan automáticamente.</p>')
      + '</div>';
  }).join('') + '</div>';
}
function bindMakerEditor() {
  document.querySelectorAll('.maker-editor').forEach(box => box.onclick = e => e.stopPropagation());
  document.querySelectorAll('.mk-include').forEach(i => i.onchange = () => { updateChoice(i.dataset.key, {include: i.checked}); saveMakerChoices(); });
  document.querySelectorAll('.mk-as-new').forEach(b => b.onclick = () => { updateChoice(b.dataset.key, {existing: null}); saveMakerChoices(); });
  document.querySelectorAll('.mk-as-existing').forEach(b => b.onclick = () => {
    const entry = makerEntries().find(x => x.key === b.dataset.key);
    if (entry?.suggested) { updateChoice(b.dataset.key, {existing: entry.suggested.number}); saveMakerChoices(); }
  });
  document.querySelectorAll('.mk-supplier').forEach(i => i.onchange = () => { updateChoice(i.dataset.key, {supplierMode: i.value}); saveMakerChoices(); });
  document.querySelectorAll('.mk-update').forEach(i => i.onchange = () => { updateChoice(i.dataset.key, {update: {[i.dataset.role]: i.checked}}); saveMakerChoices(); });
  document.querySelectorAll('.mk-value').forEach(i => i.oninput = () => { updateChoice(i.dataset.key, {values: {[i.dataset.role]: i.value}}); saveMakerChoices(false); });
  document.querySelectorAll('.mk-confirm').forEach(b => b.onclick = e => { e.stopPropagation(); confirmMakers(); });
  document.querySelectorAll('.mk-unlock').forEach(b => b.onclick = async e => { e.stopPropagation(); try { await unconfirmMakers(); } catch (err) { toast(err.message, true); } });
  document.querySelectorAll('.mk-none').forEach(b => b.onclick = e => { e.stopPropagation(); makerEntries().forEach(x => updateChoice(x.key, {include: false})); saveMakerChoices(); });
}

let reviewSignature = '';
function reviewFields() {
  return (state?.fields || []).filter(f => f.proposals.length || f.approved != null || f.rejected)
    .sort((a, b) => (b.kind === 'manufacturer') - (a.kind === 'manufacturer') || Number(a.id) - Number(b.id));
}
function reviewStatus(f, plan = makerPlan()) {
  if (f.kind === 'manufacturer') return makersConfirmed() ? 'approved' : f.rejected ? 'rejected' : 'pending';
  if (f.approved != null) return 'approved';
  if (f.rejected) return 'rejected';
  if (f.kind === 'range_add' && !planRangeLines(f, plan).length) return 'rejected';
  return 'pending';
}
function changeColors() {
  const colors = {};
  reviewFields().forEach((f, i) => colors[f.id] = i % PALETTE_SIZE);
  const maker = makerField();
  if (maker && maker.id in colors) Object.keys(makerPlan().derived).concat(makerChoices.derivedIds || []).forEach(id => colors[id] = colors[maker.id]);
  return colors;
}
// Valor que se muestra en el documento para un cambio por revisar: la primera opción de cada fabricante.
function draftValue(f, plan = makerPlan()) {
  if (f.approved != null) return f.approved;
  if (f.rejected || !f.proposals.length) return null;
  if (f.kind === 'manufacturer') return plan.value || null;
  if (f.kind === 'range_add') {
    const lines = planRangeLines(f, plan);
    return lines.length ? lines.map(l => 'Fabricante: ' + l.maker + ' | ' + l.value).join('\n') : null;
  }
  const groups = ProposalGroups.group(f);
  return f.proposals[groups[0].variants[0].index].value;
}
function draftChanges() {
  const plan = makerPlan(), draft = {};
  reviewFields().forEach(f => { if (reviewStatus(f, plan) === 'pending') { const v = draftValue(f, plan); if (v) draft[f.id] = v; } });
  if (!makersConfirmed()) Object.assign(draft, plan.derived);
  return draft;
}
function optionCount(f) {
  if (f.kind === 'range_add') return ProposalGroups.rangeMakers(f).filter(m => m.variants.length > 1).length;
  return Math.max(0, ProposalGroups.group(f).length - 1);
}
function shownValue(f, plan) {
  const value = draftValue(f, plan) ?? (f.proposals.length ? f.proposals[0].value : '');
  if (f.kind === 'range_add') return ProposalGroups.rangeResult(f.cell, existingNumbers(), state.manufacturer_numbers || {}, value).text;
  return value;
}
function renderReview() {
  if (!state || currentPage !== 'review') return;
  syncMakerChoices();
  const fields = reviewFields(), colors = changeColors(), plan = makerPlan();
  const signature = JSON.stringify([fields.map(f => [f.id, f.approved, f.rejected, f.proposals.length]), makerChoices, reviewFilter, previewSkipped, activeChange, state.manufacturer_numbers, state.busy]);
  if (signature === reviewSignature) return schedulePreview();
  // No se reconstruye la lista mientras se escribe en un dato de fabricante.
  if (document.activeElement?.classList.contains('mk-value')) return schedulePreview();
  reviewSignature = signature;
  const statuses = Object.fromEntries(fields.map(f => [f.id, reviewStatus(f, plan)]));
  const counts = {all: fields.length, pending: 0, approved: 0, rejected: 0};
  fields.forEach(f => counts[statuses[f.id]]++);
  Object.entries(counts).forEach(([k, v]) => $('filter-' + k).textContent = v);
  document.querySelectorAll('.review-filters .chip').forEach(b => b.classList.toggle('active', b.dataset.filter === reviewFilter));
  $('review-summary').textContent = fields.length
    ? counts.approved + ' conforme(s) · ' + counts.pending + ' por revisar · ' + counts.rejected + ' quitado(s). Solo los conformes se exportan.'
    : 'No hay cambios propuestos. Usa «Cambio manual» en el expediente para editar un campo.';
  $('review-accept-all').disabled = state.busy || !counts.pending;
  $('review-export').disabled = state.busy || !(counts.approved + counts.pending);
  const pendingMakers = makerField()?.proposals.length && !makersConfirmed();
  const visible = fields.filter(f => reviewFilter === 'all' || statuses[f.id] === reviewFilter);
  $('review-list').innerHTML = visible.length ? visible.map(f => {
    const status = statuses[f.id], skipped = previewSkipped[f.id];
    if (f.kind === 'manufacturer') {
      const actions = makersConfirmed()
        ? '<button class="secondary small mk-unlock">Cambiar selección</button>'
        : '<button class="primary small mk-confirm">✓ Confirmar fabricantes</button><button class="secondary small mk-none">Ninguno va</button>';
      return '<li class="review-item maker-item is-' + status + (activeChange === f.id ? ' active' : '') + '" data-id="' + esc(f.id) + '">'
        + '<span class="swatch chg-' + colors[f.id] + '" aria-hidden="true"></span><div class="review-item-body">'
        + '<div class="review-item-top"><span class="eyebrow">SECCIÓN B · PRIMERO</span><span class="status ' + (status === 'approved' ? 'approved' : 'pending') + '">' + (status === 'approved' ? 'Confirmado' : 'Por revisar') + '</span></div>'
        + '<strong class="review-item-title">Fabricantes y proveedores detectados</strong>'
        + '<p class="review-hint">Marca los que van y corrige fabricante o proveedor si hace falta. Los rangos de la sección A de un fabricante que no va se quitan solos.</p>'
        + makerEditor(f)
        + '<div class="review-actions">' + actions + '<button class="text-button review-detail" data-id="' + esc(f.id) + '">Ver respaldo</button></div>'
        + '</div></li>';
    }
    const options = optionCount(f);
    const lines = f.kind === 'range_add' ? planRangeLines(f, plan) : [];
    const waits = f.kind === 'range_add' && pendingMakers && lines.some(l => l.isNew);
    const autoRemoved = f.kind === 'range_add' && !f.rejected && f.approved == null && !lines.length;
    const label = autoRemoved ? 'No aplica' : {approved: 'Conforme', rejected: 'Quitado', pending: 'Por revisar'}[status];
    const before = beforeText(f) || '—';
    const actions = autoRemoved ? ''
      : status === 'rejected'
      ? '<button class="secondary small review-restore" data-id="' + esc(f.id) + '">Volver a incluir</button>'
      : (status === 'approved' ? '' : '<button class="primary small review-ok" data-id="' + esc(f.id) + '"' + (waits ? ' disabled title="Confirma primero los fabricantes"' : '') + '>✓ Conforme</button>')
        + '<button class="secondary small review-remove" data-id="' + esc(f.id) + '">Quitar</button>';
    return '<li class="review-item is-' + status + (activeChange === f.id ? ' active' : '') + '" data-id="' + esc(f.id) + '">'
      + '<span class="swatch chg-' + colors[f.id] + '" aria-hidden="true"></span><div class="review-item-body">'
      + '<div class="review-item-top"><span class="eyebrow">' + (f.section === 'ID' ? 'IDENTIFICACIÓN' : 'SECCIÓN ' + esc(f.section)) + '</span><span class="status ' + {approved: 'approved', rejected: 'manual', pending: 'pending'}[status] + '">' + label + '</span></div>'
      + '<strong class="review-item-title">' + esc(f.label) + '</strong>'
      + (autoRemoved ? '<p class="review-hint">Su fabricante no se incorpora, así que este cambio no se aplica.</p>'
        : '<div class="review-diff">' + (['manufacturer', 'additional', 'add', 'range_add'].includes(f.kind) ? '' : '<del>' + esc(before) + '</del>') + '<ins>' + esc(shownValue(f, plan) || '—') + '</ins></div>')
      + (waits && status === 'pending' ? '<p class="review-hint">Se podrá marcar cuando confirmes los fabricantes.</p>' : '')
      + (options && status === 'pending' ? '<p class="review-hint">Hay ' + options + ' alternativa(s); se muestra la primera. Elige otra en «Ver respaldo y editar».</p>' : '')
      + (skipped && status === 'pending' ? '<p class="review-hint warn">No se aplica en la vista: ' + esc(skipped) + '</p>' : '')
      + '<div class="review-actions">' + actions + '<button class="text-button review-detail" data-id="' + esc(f.id) + '">Ver respaldo y editar</button></div>'
      + '</div></li>';
  }).join('') : '<li class="review-empty">' + (fields.length ? 'No hay cambios en este filtro.' : 'Sin cambios para revisar.') + '</li>';
  document.querySelectorAll('.review-ok').forEach(b => b.onclick = e => { e.stopPropagation(); acceptChange(b.dataset.id); });
  document.querySelectorAll('.review-remove').forEach(b => b.onclick = async e => { e.stopPropagation(); try { await perform('reject', {id: b.dataset.id}); } catch {} });
  document.querySelectorAll('.review-restore').forEach(b => b.onclick = async e => { e.stopPropagation(); try { await perform('restore', {id: b.dataset.id}); } catch {} });
  document.querySelectorAll('.review-detail').forEach(b => b.onclick = e => { e.stopPropagation(); editField(b.dataset.id); });
  document.querySelectorAll('.review-item').forEach(li => li.onclick = () => focusChange(li.dataset.id));
  bindMakerEditor();
  schedulePreview();
}
async function acceptChange(id) {
  const f = state.fields.find(x => x.id === id);
  const value = f && draftValue(f);
  if (!value) return;
  try { await perform('approve', {id, value}); toast('Cambio marcado como conforme.'); }
  catch { if (f.kind === 'range_add') editField(id); }
}
async function acceptAll() {
  $('review-accept-all').disabled = true;
  const maker = makerField();
  if (maker?.proposals.length && !makersConfirmed() && !(await confirmMakers())) return;
  const failed = [];
  const pending = reviewFields().filter(f => f.kind !== 'manufacturer' && reviewStatus(f) === 'pending').sort((a, b) => (a.kind === 'range_add') - (b.kind === 'range_add'));
  for (const f of pending) {
    // El estado se relee: los rangos dependen de los fabricantes recién aprobados.
    const current = state.fields.find(x => x.id === f.id);
    const value = current && draftValue(current);
    if (!value) continue;
    try { await api('approve', {id: f.id, value}); await refresh(); }
    catch (e) { failed.push(f.label + ': ' + e.message); }
  }
  await refresh();
  toast(failed.length ? failed.length + ' cambio(s) requieren tu revisión: ' + failed[0] : 'Todos los cambios incluidos quedaron conformes.', !!failed.length);
}
function focusChange(id) {
  activeChange = id;
  document.querySelectorAll('.review-item').forEach(li => li.classList.toggle('active', li.dataset.id === id));
  const target = document.querySelector('#word-preview [data-change="' + CSS.escape(id) + '"]');
  if (target) {
    target.scrollIntoView({behavior: 'smooth', block: 'center'});
    target.classList.remove('flash'); void target.offsetWidth; target.classList.add('flash');
  } else if ($('preview-mode').value === 'pages') {
    toast('En Páginas reales ubica el cambio por su color. La Vista de contenido permite saltar a cada cambio.');
  }
}
function previewPayload() {
  return {fecha: revisionDate, add_history: addHistory, history_text: historyEdited ? historyText : null,
          mode: $('preview-mode').value, draft: draftChanges(), colors: changeColors()};
}
function schedulePreview(force = false) {
  if (currentPage !== 'review' || !state?.word) return;
  const payload = previewPayload();
  const signature = JSON.stringify([payload, state.fields.filter(f => f.approved != null).map(f => [f.id, f.approved])]);
  if (!force && signature === previewSignature) return;
  previewSignature = signature;
  clearTimeout(previewTimer);
  previewTimer = setTimeout(updatePreview, force ? 0 : 450);
}
function previewLoading() {
  $('word-preview').setAttribute('aria-busy', 'true');
  if (!$('word-preview').querySelector('.document-page, table, p'))
    $('word-preview').innerHTML = '<div class="preview-message" role="status"><span class="spinner"></span><h3>Preparando el documento…</h3><p>Aplicamos los cambios incluidos a una copia del Word.</p></div>';
  else $('word-preview').classList.add('refreshing');
}
async function updatePreview() {
  const request = ++previewRequest;
  addHistory = $('history-enabled').checked;
  revisionDate = $('preview-date').value || revisionDate;
  $('preview-error').textContent = '';
  previewLoading();
  $('refresh-preview').disabled = true;
  try {
    const payload = previewPayload();
    if (!historyEdited) {
      historyText = (await api('history', {draft: payload.draft})).text;
      if (request !== previewRequest) return;
      $('history-text').value = historyText;
    }
    const result = await api('preview', payload);
    if (request !== previewRequest) return;
    previewSkipped = Object.fromEntries((result.skipped || []).map(s => [s.id, s.error]));
    const pending = Object.keys(payload.draft).length;
    const notice = !reviewFields().length ? 'Documento vigente: no hay cambios propuestos.'
      : addHistory && !(historyEdited ? historyText : $('history-text').value).trim() ? 'Completa la revisión histórica o desactiva su registro antes de exportar.' : '';
    $('review-doc-info').textContent = pending ? pending + ' cambio(s) por revisar se muestran como si estuvieran aprobados. Cada color corresponde a una tarjeta.' : 'Cada cambio incluido se resalta con el color de su tarjeta.';
    $('word-preview').innerHTML = (notice ? '<div class="preview-notice" role="status">' + esc(notice) + '</div>' : '')
      + (result.pages ? result.pages.map((src, i) => '<figure class="document-page"><figcaption>Página ' + (i + 1) + ' · ' + esc(result.renderer) + '</figcaption><img src="' + src + '" alt="Página ' + (i + 1) + ' del Word"></figure>').join('') : result.html);
    renderReviewSkips();
  } catch (e) {
    if (request !== previewRequest) return;
    previewSignature = '';
    $('preview-error').textContent = e.message;
    $('word-preview').innerHTML = '<div class="preview-message" role="alert"><h3>No se pudo generar la vista previa</h3><p>' + esc(e.message) + '</p><p>Quita el cambio que lo provoca, edítalo, o cambia a Vista de contenido y pulsa Actualizar.</p></div>';
  } finally {
    if (request === previewRequest) { $('word-preview').setAttribute('aria-busy', 'false'); $('word-preview').classList.remove('refreshing'); $('refresh-preview').disabled = false; }
  }
}
function renderReviewSkips() {
  // Vuelve a pintar las tarjetas sin pedir otra vista previa.
  const signature = previewSignature;
  reviewSignature = '';
  renderReview();
  previewSignature = signature;
  clearTimeout(previewTimer);
}
function openReview() {
  if (!state?.word) return toast('Carga primero la especificación vigente.', true);
  $('preview-date').value = revisionDate;
  $('history-enabled').checked = addHistory;
  previewSignature = '';
  reviewSignature = '';
  navigate('review');
}
$('preview-button').onclick = openReview;
$('review-back').onclick = () => navigate('workspace');
$('review-accept-all').onclick = acceptAll;
document.querySelectorAll('.review-filters .chip').forEach(b => b.onclick = () => { reviewFilter = b.dataset.filter; renderReview(); });
$('refresh-preview').onclick = () => schedulePreview(true);
$('preview-mode').onchange = () => schedulePreview(true);
$('history-enabled').onchange = () => schedulePreview(true);
$('preview-date').onchange = () => { revisionDate = $('preview-date').value || revisionDate; schedulePreview(true); };
$('history-text').oninput = () => { historyEdited = true; historyText = $('history-text').value; };
$('history-text').onchange = () => schedulePreview(true);
$('regenerate-history').onclick = () => { historyEdited = false; schedulePreview(true); };
$('review-export').onclick = async () => {
  const pending = reviewFields().filter(f => reviewStatus(f) === 'pending').length;
  if (pending && confirm(pending + ' cambio(s) siguen por revisar. Solo se exportan los conformes.\n\n¿Marcarlos como conformes antes de exportar?')) await acceptAll();
  if (!state.approved_count) return toast('Marca al menos un cambio como conforme antes de exportar.', true);
  openExport();
};
$('export-button').onclick = () => openExport();
$('create-export').onclick = async () => {
  const button=$('create-export');
  try {
    if (!$('export-applicant').value.trim() || !$('export-area').value.trim() || !$('export-date').value || !$('export-folder').value) throw new Error('Completa solicitante, área, fecha y carpeta de destino.');
    button.disabled=true;button.textContent='Creando expediente…';
    const result=await perform('export',{salida:$('export-folder').value,solicitante:$('export-applicant').value,area:$('export-area').value,fecha:$('export-date').value,add_history:addHistory,history_text:historyEdited?historyText:null});
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
      else if(state.fields.some(f=>f.proposals.length)&&currentPage==='workspace')openReview();
    }
  }catch(e){toast(e.message,true);}
  setTimeout(poll,state?.busy?1000:4000);
}
poll();

/* Técnicas del laboratorio: tabla con búsqueda y filtro por categoría. */
let techniques = null, techniqueFilter = 'Todas', openTechnique = null;
async function loadTechniques() {
  if (techniques) return renderTechniques();
  $('techniques-list').innerHTML = '<div class="preview-message"><span class="spinner"></span></div>';
  try { techniques = (await api('techniques')).items; renderTechniques(); }
  catch (e) { $('techniques-list').innerHTML = ''; toast(e.message, true); }
}
function renderTechniques() {
  const query = foldText($('techniques-search').value);
  const categories = ['Todas', ...new Set(techniques.map(t => t.categoria))];
  $('techniques-count').textContent = techniques.length + ' técnicas';
  $('techniques-filters').innerHTML = categories.map(c => '<button class="chip' + (c === techniqueFilter ? ' active' : '') + '" data-category="' + esc(c) + '">' + esc(c)
    + ' <span>' + (c === 'Todas' ? techniques.length : techniques.filter(t => t.categoria === c).length) + '</span></button>').join('');
  $('techniques-filters').querySelectorAll('.chip').forEach(b => b.onclick = () => { techniqueFilter = b.dataset.category; renderTechniques(); });
  const rows = techniques.filter(t => (techniqueFilter === 'Todas' || t.categoria === techniqueFilter)
    && (!query || foldText(t.codigo + ' ' + t.titulo + ' ' + t.objetivo).includes(query)));
  $('techniques-list').innerHTML = rows.length ? '<table class="techniques-table"><thead><tr><th>Código</th><th>Técnica</th><th>Categoría</th><th>Versión</th></tr></thead><tbody>'
    + rows.map(t => '<tr class="technique-row' + (openTechnique === t.codigo ? ' open' : '') + '" data-code="' + esc(t.codigo) + '">'
      + '<td><code>' + esc(t.codigo) + '</code>' + (t.en_uso ? '<span class="tech-used">En este Word</span>' : '') + '</td>'
      + '<td><strong>' + esc(t.titulo) + '</strong><small class="tech-objective">' + esc(t.objetivo || 'Sin objetivo legible en el documento.') + '</small></td>'
      + '<td><span class="tech-category">' + esc(t.categoria) + '</span></td><td>' + (t.version ? 'V' + esc(t.version) : '—') + '</td></tr>'
      + (openTechnique === t.codigo ? '<tr class="technique-detail-row"><td colspan="4"><p><b>Objetivo</b>' + esc(t.objetivo || '—') + '</p>'
        + '<details><summary>Texto leído del documento' + (t.ocr ? ' (OCR)' : '') + '</summary><pre class="technique-detail">' + esc(t.texto) + '</pre></details></td></tr>' : '')).join('')
    + '</tbody></table>' : '<p class="helper">Ninguna técnica coincide con la búsqueda.</p>';
  $('techniques-list').querySelectorAll('.technique-row').forEach(r => r.onclick = () => { openTechnique = openTechnique === r.dataset.code ? null : r.dataset.code; renderTechniques(); });
}
$('techniques-card').ontoggle = () => { if ($('techniques-card').open) loadTechniques(); };
$('techniques-search').oninput = () => techniques && renderTechniques();

$('commercial-notes').onclick=()=>showTab('notes');
$('commercial-manual').onclick=()=>{const f=state.fields.find(f=>f.kind==='manufacturer');if(f)editField(f.id);};

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

/* Estado de las claves de API: última respuesta de cada clave y pruebas a pedido. */
const PROVIDERS = [
  {id: 'gemini', name: 'Google Gemini', setting: 'modelo', fallback: '',
   hint: 'Lee también PDF escaneados. Si el modelo elegido está saturado o sin cuota, se usan los otros automáticamente.',
   models: null},
  {id: 'groq', name: 'Groq', setting: 'groq_model', fallback: 'openai/gpt-oss-120b',
   hint: 'Muy rápido; solo para PDF con texto seleccionable.',
   models: [['openai/gpt-oss-120b', 'openai/gpt-oss-120b · recomendado'], ['openai/gpt-oss-20b', 'openai/gpt-oss-20b · más liviano'],
            ['llama-3.3-70b-versatile', 'llama-3.3-70b-versatile'], ['llama-3.1-8b-instant', 'llama-3.1-8b-instant']]},
  {id: 'openrouter', name: 'OpenRouter', setting: 'openrouter_model', fallback: '',
   hint: 'Respaldo con modelos gratuitos de varios proveedores (lista actualizada desde OpenRouter).', models: null},
];
const KEY_STATUS = {ok: 'Responde', saturada: 'Saturada', invalida: 'Inválida', error: 'Con error', sin_uso: 'Sin uso aún'};
let keysHealthTimer = null, keyRows = [], openrouterModels = null, geminiModels = null, keysSignature = '';
function modelOptions(p) {
  let options;
  if (p.id === 'openrouter') {
    if (!openrouterModels) return '<option value="">Cargando modelos gratuitos…</option>';
    options = openrouterModels.models.map((m, i) => [m.id, m.name.replace(/\s*\(free\)\s*$/i, '') + (i === 0 ? ' · recomendado' : '') + (m.pdf ? ' · lee PDF' : '') + (m.context ? ' · ' + Math.round(m.context / 1000) + 'k' : '')]);
  } else if (p.id === 'gemini') {
    // Lista real de la API (los modelos se retiran con el tiempo); cada modelo tiene su propia cuota diaria.
    const list = geminiModels?.models?.length ? geminiModels.models : ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.5-flash'];
    options = list.map((m, i) => [m, m + (i === 0 ? ' · recomendado (el más nuevo)' : /lite$/.test(m) ? ' · más rápido' : '')]);
  } else options = p.models.slice();
  const value = state?.settings?.[p.setting] || (p.id === 'openrouter' ? options[0]?.[0] : p.fallback);
  if (value && !options.some(o => o[0] === value)) options.unshift([value, value + ' (actual)']);
  return options.map(([v, l]) => '<option value="' + esc(v) + '"' + (v === value ? ' selected' : '') + '>' + esc(l) + '</option>').join('')
    + (p.id === 'openrouter' ? '<option value="__other">Otro modelo…</option>' : '');
}
function keyRow(r) {
  return '<tr><td><code>' + esc(r.masked) + '</code><small>' + esc(r.source) + '</small></td>'
    + '<td><span class="key-status ' + esc(r.status) + '">' + esc(KEY_STATUS[r.status] || r.status) + '</span>'
    + (r.status === 'saturada' && r.saturated_at ? '<small>desde ' + esc(formatDate(r.saturated_at)) + '</small>' : '') + '</td>'
    + '<td>' + (r.last_at ? esc(formatDate(r.last_at)) + '<small>' + esc(r.last_message || '') + (r.last_code ? ' (' + esc(r.last_code) + ')' : '') + (r.last_seconds != null ? ' · ' + esc(r.last_seconds) + ' s' : '') + '</small>' : '—') + (r.detail ? '<small>' + esc(r.detail) + '</small>' : '') + '</td>'
    + '<td class="key-uses">' + r.ok + ' bien<small>' + r.fail + ' ' + (r.fail === 1 ? 'fallo' : 'fallos') + '</small></td>'
    + '<td class="key-actions"><button class="secondary small key-test" data-id="' + esc(r.id) + '">Probar</button>'
    + (r.source === 'configuración' ? '<button class="text-button key-delete" data-id="' + esc(r.id) + '" data-provider="' + esc(r.provider) + '">Eliminar</button>' : '') + '</td></tr>';
}
function renderKeysHealth(rows) {
  keyRows = rows;
  const counts = rows.reduce((a, r) => (a[r.status] = (a[r.status] || 0) + 1, a), {});
  const indicator = $('keys-indicator');
  if (indicator) {
    const bad = (counts.saturada || 0) + (counts.invalida || 0) + (counts.error || 0), ok = counts.ok || 0;
    indicator.className = 'keys-indicator' + (rows.length ? '' : ' hidden') + (counts.invalida || counts.error ? ' bad' : counts.saturada ? ' warn' : ' good');
    indicator.textContent = 'Claves: ' + ok + (ok === 1 ? ' responde' : ' responden') + (bad ? ' · ' + bad + ' con ' + (bad === 1 ? 'problema' : 'problemas') : '');
  }
  const box = $('keys-health');
  // No se redibuja mientras se escribe una clave o se elige un modelo, ni si nada cambió.
  const signature = JSON.stringify([rows, state?.settings, !!openrouterModels, geminiModels?.models]);
  if (!box || box.contains(document.activeElement) || signature === keysSignature) return;
  keysSignature = signature;
  box.innerHTML = (rows.length ? '' : '<p class="warning">Para comenzar, agrega al menos una clave de API. Gemini es la opción recomendada.</p>')
    + PROVIDERS.map(p => {
      const mine = rows.filter(r => r.provider === p.id);
      return '<div class="provider-block"><div class="provider-head"><div><strong>' + esc(p.name) + '</strong> <span class="provider-count">' + mine.length + ' clave(s)</span><small>' + esc(p.hint) + '</small></div>'
        + '<label class="provider-model">Modelo<select class="model-choice" data-provider="' + p.id + '">' + modelOptions(p) + '</select></label></div>'
        + (mine.length ? '<table class="keys-table"><thead><tr><th>Clave</th><th>Estado</th><th>Última respuesta</th><th>Usos</th><th></th></tr></thead><tbody>' + mine.map(keyRow).join('') + '</tbody></table>' : '')
        + '<div class="input-row add-key-row"><input type="password" class="new-key" data-provider="' + p.id + '" autocomplete="off" placeholder="Pega una clave de ' + esc(p.name) + '">'
        + '<button class="secondary add-key-btn" data-provider="' + p.id + '">Agregar clave</button><button class="text-button get-key" data-provider="' + p.id + '">Obtener una clave ↗</button></div></div>';
    }).join('');
  box.querySelectorAll('.key-test').forEach(b => b.onclick = () => testKeys({id: b.dataset.id}, b));
  box.querySelectorAll('.key-delete').forEach(b => b.onclick = async () => {
    if (!confirm('¿Eliminar esta clave de la aplicación? Dejará de usarse en los análisis.')) return;
    try { renderKeysHealth((await api('key_delete', {provider: b.dataset.provider, id: b.dataset.id})).keys); await refresh(); toast('Clave eliminada.'); }
    catch (e) { toast(e.message, true); }
  });
  box.querySelectorAll('.get-key').forEach(b => b.onclick = async () => { try { await api('open_url', {provider: b.dataset.provider}); } catch (e) { toast(e.message, true); } });
  box.querySelectorAll('.new-key').forEach(i => i.onkeydown = e => { if (e.key === 'Enter') box.querySelector('.add-key-btn[data-provider="' + i.dataset.provider + '"]').click(); });
  box.querySelectorAll('.add-key-btn').forEach(b => b.onclick = async () => {
    const input = box.querySelector('.new-key[data-provider="' + b.dataset.provider + '"]');
    const value = input.value.trim();
    if (!value) return toast('Pega la clave antes de agregarla.', true);
    try {
      await api('credentials', {[b.dataset.provider]: value});
      input.value = ''; input.blur();
      await refresh();
      toast('Clave agregada. Comprobando que responda…');
      await testKeys({provider: b.dataset.provider}, b);
    } catch (e) { toast(e.message, true); }
  });
  box.querySelectorAll('.model-choice').forEach(sel => sel.onchange = async () => {
    const p = PROVIDERS.find(x => x.id === sel.dataset.provider);
    let value = sel.value;
    if (value === '__other') {
      value = (prompt('Identificador del modelo en OpenRouter (por ejemplo, proveedor/modelo:free):') || '').trim();
      if (!value) { sel.blur(); keysSignature = ''; renderKeysHealth(keyRows); return; }
    }
    try { await api('settings', {[p.setting]: value}); await refresh(); toast('Modelo de ' + p.name + ' guardado: ' + value); }
    catch (e) { toast(e.message, true); }
    sel.blur(); keysSignature = ''; renderKeysHealth(keyRows);
  });
  if (!openrouterModels) api('openrouter_models').then(r => { openrouterModels = r; renderKeysHealth(keyRows); }).catch(() => {});
  if (!geminiModels && rows.some(r => r.provider === 'gemini')) { geminiModels = {models: []}; api('gemini_models').then(r => { geminiModels = r; renderKeysHealth(keyRows); }).catch(() => {}); }
}
async function loadKeysHealth() {
  clearTimeout(keysHealthTimer);
  try { renderKeysHealth((await api('keys_health')).keys); } catch {}
  keysHealthTimer = setTimeout(loadKeysHealth, currentPage === 'settings' ? 10000 : 30000);
}
async function testKeys(filter = {}, button = $('keys-test')) {
  const label = button.textContent;
  button.disabled = true; button.textContent = 'Probando…';
  try { renderKeysHealth((await api('keys_test', filter)).keys); }
  catch (e) { toast(e.message, true); }
  finally { button.disabled = false; button.textContent = label; }
}
if ($('keys-test')) $('keys-test').onclick = () => testKeys();
function showKeys() { navigate('settings'); setTimeout(() => $('keys-health-card').scrollIntoView({behavior: 'smooth'}), 100); }
if ($('keys-indicator')) $('keys-indicator').onclick = showKeys;
loadKeysHealth();
