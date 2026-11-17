/* Display-only grouping. Exact source values and evidence remain untouched. */
(function(root){
  const fold = v => String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const entityKey = v => fold(v).replace(/[^a-z0-9]/g,'');
  function valueKey(v,sensory=false){
    const raw=String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'');
    const normalized=(/[0-9]/.test(raw)?raw:raw.toLowerCase()).replace(/(\d),(?=\d)/g,'$1.').replace(/\s+/g,' ').trim();
    if(sensory && !/[0-9%<>≤≥=]/.test(normalized) && !/\b(sin|no|excepto|ausencia|libre)\b/.test(normalized)){
      // Only exact words are reordered; negation and extra qualifiers are retained.
      return normalized.replace(/[.,;:]/g,' ').split(/\s+/).filter(w=>w&&!['y','e','de','del','el','la','los','las'].includes(w)).sort().join(' ');
    }
    return normalized.replace(/[.,;:]$/,'').replace(/\s+/g,' ');
  }
  // Etiquetas pegadas por la IA ("…LTD.Proveedor:") y líneas vacías no forman parte del nombre.
  const LABELS='Proveedor|Nombre comercial|Tiempo de vida [uú]til|Almacenamiento|Par[aá]metro adicional';
  function normalizeBlock(value){
    return String(value??'').replace(new RegExp('(?<=\\S)\\s*(?=(?:'+LABELS+')\\s*:)','gi'),'\n')
      .split(/\r?\n/).filter(line=>line.trim()&&!/^[^:]+:\s*$/.test(line)).join('\n');
  }
  function describe(field,p){
    const value=field.kind==='manufacturer'?normalizeBlock(p.value):String(p.value??'');
    const match=value.match(/^fabricante\s*:\s*(.+?)(?:\r?\n|\s*\||$)/i);
    const maker=match?.[1].trim()||'';
    const detail=field.kind==='range_add'?value.slice(value.indexOf(' | ')+3).replace(/(\s*\|)+\s*$/,'').trim():value;
    return {maker,detail};
  }
  function blockKey(value){
    return String(value).split(/\r?\n/).map(line=>{const i=line.indexOf(':');if(i<0)return valueKey(line);const role=fold(line.slice(0,i)).trim();const v=line.slice(i+1);return role+':'+(/^(fabricante|proveedor)$/.test(role)?entityKey(v):valueKey(v));}).sort().join('\n');
  }
  function group(field){
    const groups=[];
    const sensory=/\b(aspecto|apariencia|color|olor|textura)\b/i.test(field.label||'');
    (field.proposals||[]).forEach((p,index)=>{
      const d=describe(field,p);
      const key=field.kind==='manufacturer'?'maker:'+entityKey(d.maker||p.value):
        (field.kind==='range_add'?'maker:'+entityKey(d.maker)+'|':'')+valueKey(d.detail,sensory);
      let g=groups.find(g=>g.key===key);
      if(!g){g={key,maker:d.maker,detail:d.detail,members:[],variants:[]};groups.push(g);}
      const member={...p,index};g.members.push(member);
      // Keep complementary manufacturer blocks as selectable alternatives, not merged data.
      const variantKey=field.kind==='manufacturer'?blockKey(p.value):valueKey(d.detail,sensory);
      let variant=g.variants.find(v=>v.key===variantKey);
      if(!variant){variant={key:variantKey,value:p.value,index,sources:[]};g.variants.push(variant);}
      variant.sources.push(member);
    });
    return groups;
  }
  // Combina los bloques comerciales de un mismo fabricante dato por dato. Solo hay que elegir
  // cuando dos fuentes dan valores realmente distintos para el mismo dato.
  function mergeManufacturer(g){
    const rows=[];
    g.members.forEach(m=>normalizeBlock(m.value).split(/\r?\n/).forEach(line=>{
      const i=line.indexOf(':');if(i<0)return;
      const role=line.slice(0,i).trim(),text=line.slice(i+1).trim();if(!text)return;
      const rk=fold(role).trim();
      const key=rk==='parametro adicional'?'pa:'+valueKey(text.split('|')[0]):rk;
      let row=rows.find(r=>r.key===key);
      if(!row){row={key,role,options:[]};rows.push(row);}
      const ok=/^(fabricante|proveedor)$/.test(rk)?entityKey(text):valueKey(text);
      let option=row.options.find(o=>o.key===ok);
      if(!option){option={key:ok,value:text,sources:[]};row.options.push(option);}
      if(!option.sources.some(s=>s.index===m.index))option.sources.push(m);
    }));
    const rank=r=>r.key==='fabricante'?0:r.key==='proveedor'?1:r.key.startsWith('pa:')?3:2;
    return rows.map((r,i)=>({r,i})).sort((a,b)=>rank(a.r)-rank(b.r)||a.i-b.i).map(x=>x.r);
  }
  function composeBlock(rows,choice={}){
    return rows.map(r=>r.role+': '+(r.options[choice[r.key]??0]||r.options[0]).value).join('\n');
  }
  // Celda RANGO resultante: (n) identifica al fabricante numerado en B.
  function rangeEntries(text){
    const out=[];
    String(text??'').split(/\r?\n/).forEach(line=>{
      const m=line.match(/^\s*\((\d+)\)\s*(.*)$/);
      if(m)out.push({n:Number(m[1]),text:m[2].trim()});
      else if(line.trim()&&out.length)out[out.length-1].text+=' '+line.trim();
      else if(line.trim())out.push({n:null,text:line.trim(),common:true});
    });
    return out;
  }
  function rangeResult(cell,existing,numbers,value){
    let entries=rangeEntries(cell);
    if(entries.length&&entries.every(e=>e.common))entries=existing.map(n=>({n,text:entries.map(e=>e.text).join(' ')}));
    const pending=[];
    String(value??'').split(/\r?\n/).forEach(line=>{
      const m=line.match(/^\s*fabricante\s*:\s*(.+?)\s*\|\s*(.+?)\s*$/i);if(!m)return;
      const n=numbers[entityKey(m[1])]??null;
      if(n==null)pending.push(m[1]);
      entries=entries.filter(e=>n==null||e.n!==n);
      entries.push({n,text:m[2].replace(/^\(\d+\)\s*/,'').replace(/(\s*\|)+$/,''),maker:m[1]});
    });
    return {text:entries.map(e=>(e.n!=null?'('+e.n+')':'(nuevo)')+' '+e.text).join('\n'),pending};
  }
  // Propuestas de rango agrupadas por fabricante: cada fabricante aporta su propia línea (n).
  function rangeMakers(field){
    const makers=[];
    const sensory=/\b(aspecto|apariencia|color|olor|textura)\b/i.test(field.label||'');
    (field.proposals||[]).forEach((p,index)=>{
      const d=describe(field,p);const key=entityKey(d.maker);
      let m=makers.find(x=>x.key===key);
      if(!m){m={key,maker:d.maker,variants:[]};makers.push(m);}
      const vk=valueKey(d.detail,sensory);
      let v=m.variants.find(x=>x.key===vk);
      if(!v){v={key:vk,value:d.detail,sources:[]};m.variants.push(v);}
      v.sources.push({...p,index});
    });
    return makers;
  }
  const api={group,describe,entityKey,valueKey,mergeManufacturer,composeBlock,rangeEntries,rangeResult,rangeMakers,normalizeBlock};root.ProposalGroups=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
