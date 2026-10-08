const $ = id => document.getElementById(id);
const base = '/api';
const fmt = (x, digits=2) => x === null || x === undefined || !Number.isFinite(Number(x)) ? '—' : Number(x).toFixed(digits);
const setMessage = (s, problem=false) => {
  $('market-status').textContent = s;
  $('market-status').style.color = problem ? '#f5bc79' : '#6ee6c8';
};
let selectedQuote = null;
let expirations = [];
let lastTicker = null;

async function get(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch(base + path, {signal: controller.signal, cache:'no-store'});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Yahoo request failed ('+response.status+')');
    return payload;
  } finally { clearTimeout(timeout); }
}

function cell(text) {
  const node = document.createElement('td');
  node.textContent = text === null || text === undefined ? '—' : String(text);
  return node;
}

function drawTable(label, rows) {
  const block = $(label+'-market');
  const tbody = $(label+'-rows');
  tbody.replaceChildren();
  block.hidden = !rows;
  if (!rows) return;
  $(label+'-count').textContent = rows.length + ' contracts';
  for (const contract of rows) {
    const row = document.createElement('tr');
    for (const val of [
      fmt(contract.strike), fmt(contract.lastPrice), fmt(contract.bid),
      fmt(contract.ask), contract.impliedVolatility == null ? '—' : fmt(Number(contract.impliedVolatility)*100,2)+'%',
      contract.volume ?? '—', contract.openInterest ?? '—'
    ]) row.appendChild(cell(val));
    tbody.appendChild(row);
  }
}

async function loadTicker(event) {
  event?.preventDefault();
  const ticker = $('ticker-input').value.trim().toUpperCase();
  if (!/^[A-Z0-9^][A-Z0-9^._-]{0,19}$/.test(ticker)) {
    setMessage('Enter a valid ticker such as SPY or AAPL.', true); return;
  }
  $('ticker-button').disabled = true;
  $('market-expiry').disabled = true;
  $('chain-button').disabled = true;
  drawTable('calls', null); drawTable('puts', null);
  setMessage('Requesting Yahoo Finance data for '+ticker+'…');
  try {
    const results = await Promise.allSettled([
      get('/quote?ticker='+encodeURIComponent(ticker)),
      get('/expirations?ticker='+encodeURIComponent(ticker))
    ]);
    if (results[0].status==='fulfilled') {
      selectedQuote = results[0].value;
      const data=selectedQuote;
      const yieldLabel = typeof data.trailing_annual_dividend_yield==='number'
        ? (data.trailing_annual_dividend_yield*100).toFixed(2)+'%' : 'unavailable';
      $('market-quote').textContent = ticker+' $'+fmt(data.last_price)+'. Dividend yield '+yieldLabel;
      $('market-transfer').disabled = false;
    } else {
      selectedQuote=null; $('market-transfer').disabled=true;
      $('market-quote').textContent = 'Quote unavailable: '+results[0].reason.message;
    }
    if (results[1].status==='fulfilled') {
      expirations = results[1].value.expirations;
      const dropdown=$('market-expiry');dropdown.replaceChildren();
      for(const date of expirations){const option=document.createElement('option');option.value=date;option.textContent=date;dropdown.appendChild(option);}
      dropdown.disabled = false; $('chain-button').disabled=false;lastTicker=ticker;
      setMessage('Yahoo response received. Choose expiry and load the chain.');
    } else {
      setMessage('Expirations unavailable: '+results[1].reason.message,true);
    }
  } catch(err) {setMessage(err.message,true);}
  finally{$('ticker-button').disabled=false;}
}

async function loadChain() {
  if (!lastTicker || !$('market-expiry').value) return;
  $('chain-button').disabled = true;
  setMessage('Loading '+lastTicker+' '+$('market-expiry').value+' option contracts…');
  try {
    const data = await get('/chain?ticker='+encodeURIComponent(lastTicker)+
       '&expiry='+encodeURIComponent($('market-expiry').value)+'&side=both');
    drawTable('calls',data.calls);drawTable('puts',data.puts);
    setMessage('Loaded '+data.calls_count+' calls and '+data.puts_count+' puts. As received '+data.retrieved_at+'. Quotes may be delayed.');
  } catch(err){drawTable('calls',null);drawTable('puts',null);setMessage(err.message,true);}
  finally {$('chain-button').disabled=false;}
}

$('market-form').addEventListener('submit',loadTicker);
$('chain-button').addEventListener('click',loadChain);
$('market-transfer').addEventListener('click',()=>{
  if (!selectedQuote) return;
  $('S').value=Number(selectedQuote.last_price).toFixed(2);
  if(typeof selectedQuote.trailing_annual_dividend_yield==='number'){
    $('q').value=(selectedQuote.trailing_annual_dividend_yield*100).toFixed(4);
  }
  $('S').dispatchEvent(new Event('change',{bubbles:true}));
  setMessage('Spot and dividend yield updated. Volatility and rates use the values entered above.');
  document.getElementById('workbench').scrollIntoView({behavior:'smooth'});
});

(async()=>{
  try{
    await get('/health');
    $('market-controls').hidden=false;
    setMessage('LOCAL YAHOO DATA ADAPTER READY');
  } catch(err) {
    $('market-controls').hidden=true;
    $('market-status').textContent='Offline pricing mode. To enable option chains run: python -m option_lab serve';
    $('market-status').style.color='#f5bc79';
  }
})();
