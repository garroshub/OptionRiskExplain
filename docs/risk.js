const el = id => document.getElementById(id);
let current = null;
let localRisk = false;
let scenarioCases = [];
let activeScenario = null;
const fmt = (v, decimals=2) => v == null || !Number.isFinite(Number(v)) ? '—'
    : Number(v).toLocaleString('en-US', {minimumFractionDigits:decimals, maximumFractionDigits:decimals});
const usd = v => (Number(v) < 0 ? '−' : '+') + '$' + fmt(Math.abs(Number(v)));
function status(message, error=false) {
  el('risk-status').textContent = message;
  el('risk-status').classList.toggle('risk-error', error);
}
function node(tag, text, className='') {
  const n = document.createElement(tag); n.textContent = String(text);
  if (className) n.className = className;
  return n;
}
const keys = [
  ['delta','Delta'], ['gamma','Gamma'], ['vega','Vega'],
  ['theta','Theta'], ['rho','Rho'], ['dividend','Dividend yield'],
  ['approximation_residual','Approximation residual'],
  ['market_basis_change','Market/model basis change'],
];
function render(report, demo=false) {
  if (!report || !report.totals || !Array.isArray(report.positions)) throw Error('Unexpected report format');
  current = report;
  el('risk-report').hidden = false;
  el('risk-mode').textContent = demo ? 'SYNTHETIC DATA' : 'USER DATA';
  el('risk-period').textContent = report.start_date + ' to ' + report.end_date + ' (' + report.calendar_days + ' calendar day(s))';
  el('risk-pnl').textContent = usd(report.totals.observed_pnl);
  el('risk-pnl').className = report.totals.observed_pnl < 0 ? 'risk-negative' : 'risk-positive';
  el('risk-count').textContent = String(report.position_count);
  el('risk-exceptions').textContent = String(report.exception_count);
  const reconciliation = Math.abs(report.totals.reconciliation_error) < 0.0000005
    ? 0 : report.totals.reconciliation_error;
  el('risk-reconcile').textContent = '$' + fmt(reconciliation, 6);
  el('risk-threshold-display').textContent = 'Exception threshold: $' + fmt(report.exception_threshold,0);
  const max = Math.max(1,...keys.map(([key]) => Math.abs(report.totals[key])));
  const bars = el('risk-bars'); bars.replaceChildren();
  for (const [key,label] of keys) {
    const amount=report.totals[key];
    const wrap=node('div','','risk-bar-row');
    const head=node('div','','risk-bar-head');
    head.append(node('span',label),node('strong',usd(amount),amount<0?'risk-negative':'risk-positive'));
    const track=node('div','','risk-bar-track');
    const bar=node('div','','risk-bar-fill '+(amount<0?'loss':'gain'));
    bar.style.width=Math.max(.2,Math.abs(amount)/max*100).toFixed(2)+'%';
    track.append(bar);wrap.append(head,track);bars.append(wrap);
  }
  const contracts=el('risk-rows');contracts.replaceChildren();
  for (const item of report.positions) {
    const tr=document.createElement('tr');
    tr.append(node('td',item.contract),node('td',String(item.quantity)),
      node('td',usd(item.observed_pnl),item.observed_pnl<0?'risk-negative':'risk-positive'),
      node('td',usd(item.greek_explained)),
      node('td',usd(item.approximation_residual)),
      node('td',usd(item.market_basis_change)),
      node('td',item.flags.length?item.flags.join(', ').replaceAll('_',' '):'—'));
    contracts.append(tr);
  }
  const exceptions=el('risk-exception-rows');exceptions.replaceChildren();
  if (!report.exceptions.length) {
    const tr=document.createElement('tr');const td=node('td','No exceptions');
    td.colSpan=3;tr.append(td);exceptions.append(tr);
  } else for(const item of report.exceptions) {
    const tr=document.createElement('tr');
    tr.append(node('td',item.contract),node('td',item.code.replaceAll('_',' ')),
      node('td',item.amount == null ? 'Check quote' : usd(item.amount)));
    exceptions.append(tr);
  }
  status(demo ? (activeScenario?.name || 'Scenario') + ' loaded.' :
    'Calculation complete. Review the reported exceptions.');
}
function escapeCsv(v) {
  if (typeof v==='number') return String(v);
  let text=String(v??'');
  if (/^[=+@-]/.test(text)) text="'"+text;
  return '"'+text.replaceAll('"','""')+'"';
}
function download(name, content, mime) {
  const object=URL.createObjectURL(new Blob([content],{type:mime}));
  const a=document.createElement('a');a.href=object;a.download=name;
  document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(object),1500);
}
el('risk-json').addEventListener('click',()=>{
  if(current)download('option-risk-explain.json',JSON.stringify(current,null,2),'application/json');
});
el('risk-csv').addEventListener('click',()=>{
  if(!current)return;
  const fields=['contract','quantity','observed_pnl','delta','gamma','vega','theta','rho','dividend',
    'approximation_residual','market_basis_change','unexplained_pnl','flags'];
  const rows=[fields.join(',')];
  for(const item of current.positions)
    rows.push(fields.map(key=>escapeCsv(key==='flags'?item.flags.join('|'):item[key])).join(','));
  download('option-risk-explain-positions.csv',rows.join('\r\n')+'\r\n','text/csv');
});
function selectScenario(id) {
  const scenario = scenarioCases.find(item => item.id === id);
  if (!scenario) throw Error('Unknown scenario');
  activeScenario = scenario;
  el('risk-scenario').value = scenario.id;
  el('risk-scenario-label').textContent = scenario.label.toUpperCase();
  el('risk-scenario-question').textContent = scenario.question;
  el('risk-scenario-move').textContent = scenario.market_move;
  el('risk-scenario-focus').textContent = 'Risk focus: ' + scenario.focus;
  render(scenario.report, true);
}
async function loadScenarios() {
  try {
    const reply = await fetch('risk-scenarios.json', {cache:'no-store'});
    if (!reply.ok) throw Error('Scenario data unavailable');
    const payload = await reply.json();
    if (payload.schema_version !== 1 || !Array.isArray(payload.scenarios) || payload.scenarios.length !== 4)
      throw Error('Unsupported scenario data');
    scenarioCases = payload.scenarios;
    selectScenario(el('risk-scenario').value);
  } catch(err) { status('Risk scenarios could not load: ' + err.message, true); }
}
el('risk-scenario').addEventListener('change', event => {
  try {selectScenario(event.target.value);}
  catch(err) {status('Could not switch scenario: ' + err.message, true);}
});
el('risk-demo').addEventListener('click',() => {
  if (activeScenario) selectScenario(el('risk-scenario').value);
});
for (const [id,field] of [['risk-sample-start','start_csv'],['risk-sample-end','end_csv']]) {
  el(id).addEventListener('click',()=>{
    if (!activeScenario) { status('Choose a scenario first.',true); return; }
    download('option-risk-' + activeScenario.id + '-' + (field === 'start_csv' ? 'start' : 'end') + '.csv',
      activeScenario[field], 'text/csv');
  });
}
el('risk-form').addEventListener('submit',async event=>{
  event.preventDefault();
  if(!localRisk){status('Start the local Python server to process CSV files.',true);return;}
  const start=el('risk-start').files[0],end=el('risk-end').files[0];
  if(!start||!end){status('Select start and end snapshot CSV files.',true);return;}
  if(start.size>1500000||end.size>1500000){status('Each CSV must be under 1.5 MB.',true);return;}
  el('risk-run').disabled=true;
  status('Calculating P&L…');
  try{
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),20000);
    let reply;
    try {
      reply=await fetch('/api/explain',{
        method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
        body:JSON.stringify({start_csv:await start.text(),end_csv:await end.text(),
          threshold:Number(el('risk-threshold').value)})
      });
    }finally{clearTimeout(timeout);}
    const value=await reply.json();
    if(!reply.ok)throw Error(value.error || 'Attribution request failed');
    render(value,false);
  }catch(err){status('Attribution failed: '+err.message,true);}
  finally{el('risk-run').disabled=false;}
});
(async()=>{
  await loadScenarios();
  try {
    const reply=await fetch('/api/health',{cache:'no-store'});
    if(!reply.ok)throw Error('no local engine');
    const health=await reply.json();
    if(health.ok){
      localRisk=true;
      el('risk-local').textContent='Local Python server connected';
      el('risk-run').disabled=false;
    }
  } catch {
    el('risk-local').textContent='Scenario results available. Start the local Python server for CSV analysis.';
    el('risk-run').disabled=true;
  }
})();
