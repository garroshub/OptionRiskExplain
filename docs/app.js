import { priceOption } from './pricing.mjs';
const el=id=>document.getElementById(id);
const fieldIds=['S','K','term','unit','r','q','v'];
const defaults=Object.fromEntries(fieldIds.map(id=>[id,el(id).value]));
const display=x=>x===null||!Number.isFinite(x)?'n/a':x.toFixed(5);
function readInputs(){
  const value=id=>{const raw=el(id).value.trim();if(!raw)throw Error('Complete every input before calculating.');return Number(raw);};
  const scale={days:365,months:12,years:1}[el('unit').value];
  if(!scale)throw Error('Invalid expiry unit');
  return {S:value('S'),K:value('K'),T:value('term')/scale,r:value('r')/100,q:value('q')/100,v:value('v')/100};
}
function chart(p,z){
  const W=760,H=312,L=55,R=18,TOP=14,B=42;
  const min=Math.max(.01,p.S*.42),max=Math.max(p.S*1.65,p.K*1.6,min+5);
  const samples=Array.from({length:121},(_,i)=>{const spot=min+(max-min)*i/120;return {spot,...priceOption({...p,S:spot})};});
  const peak=Math.max(.01,...samples.map(s=>Math.max(s.call,s.put)))*1.08;
  const X=s=>L+(s-min)/(max-min)*(W-L-R),Y=n=>H-B-(n/peak)*(H-TOP-B);
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 '+W+' '+H);svg.setAttribute('aria-hidden','true');
  const add=(tag,attrs,label)=>{const node=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,v);if(label!==undefined)node.textContent=label;svg.appendChild(node);};
  for(let i=0;i<5;i++){
    const y=TOP+(H-TOP-B)*i/4;add('line',{x1:L,x2:W-R,y1:y,y2:y,stroke:'#315164'});
    add('text',{x:L-9,y:y+4,'text-anchor':'end','font-size':11,fill:'#9cb5c6'},(peak*(1-i/4)).toFixed(2));
    const s=min+(max-min)*i/4;add('text',{x:X(s),y:H-12,'text-anchor':'middle','font-size':11,fill:'#9cb5c6'},s.toFixed(0));
  }
  add('line',{x1:X(p.S),x2:X(p.S),y1:TOP,y2:H-B,stroke:'#94abba','stroke-dasharray':'6 6'});
  for(const [name,color] of [['call','#6ee6c8'],['put','#f5bc79']]){
    add('path',{d:samples.map((s,i)=>(i?'L':'M')+X(s.spot).toFixed(2)+' '+Y(s[name]).toFixed(2)).join(' '),stroke:color,'stroke-width':3.3,fill:'none'});
    add('circle',{cx:X(p.S),cy:Y(z[name]),r:5,fill:color,stroke:'#11293e','stroke-width':3});
  }
  add('text',{x:W-R,y:H-12,'text-anchor':'end','font-size':11,fill:'#9cb5c6'},'Spot price');
  el('curve').replaceChildren(svg);
  el('curve').setAttribute('aria-label','Theoretical call and put premiums from spot '+min.toFixed(2)+' to '+max.toFixed(2)+'. Current spot '+p.S.toFixed(2)+': call '+z.call.toFixed(4)+', put '+z.put.toFixed(4)+'.');
}
function update(){
  try{
    const p=readInputs(),z=priceOption(p);
    el('error').hidden=true;
    el('call').textContent='$'+z.call.toFixed(4);
    el('put').textContent='$'+z.put.toFixed(4);
    const keys={dc:'deltaCall',dp:'deltaPut',gc:'gamma',gp:'gamma',vc:'vega',vp:'vega',tc:'thetaCall',tp:'thetaPut',rc:'rhoCall',rp:'rhoPut'};
    for(const [id,key] of Object.entries(keys))el(id).textContent=display(z[key]);
    chart(p,z);
  }catch(error){el('error').textContent=error.message;el('error').hidden=false;}
}
el('model-form').addEventListener('submit',event=>{event.preventDefault();update()});
fieldIds.forEach(id=>el(id).addEventListener('change',update));
el('reset').addEventListener('click',()=>{fieldIds.forEach(id=>el(id).value=defaults[id]);update()});
update();
