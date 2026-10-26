const $ = id => document.getElementById(id);
const money = n => Number(n).toLocaleString('fr-FR', {minimumFractionDigits:2,maximumFractionDigits:2})+' $';
const stamp = n => new Date(n*1000).toISOString().replace('T',' ').slice(0,19);
function table(id, headers, rows) {
  const host=$(id); host.replaceChildren();
  if(!rows.length){host.textContent='Aucune donnée pour le moment.';return;}
  const t=document.createElement('table');const head=t.createTHead().insertRow();
  headers.forEach(v=>{const th=document.createElement('th');th.textContent=v;head.append(th);});
  const body=t.createTBody();rows.forEach(row=>{const tr=body.insertRow();row.forEach(v=>{tr.insertCell().textContent=v;});});host.append(t);
}
function render(s){
  const labels={running:'En cours',paused:'En pause',stopped:'Arrêtée',stopping:'Clôture en cours'};
  $('status').textContent=labels[s.mode];
  if(document.activeElement!==$('profile')) $('profile').value=s.profile;
  const p=s.profiles[s.profile];
  $('parameters').textContent=`Risque / position : ${p.risk*100} % · Perte quotidienne max. : ${p.daily_loss*100} % · Positions max. : ${p.max_positions} · Stop : ${p.stop} USD/oz · Objectif : ${p.reward} × stop · Spread : ${s.spread} · Slippage par exécution : ${s.slippage} USD/oz`;
  $('metrics').replaceChildren();
  [['Solde',money(s.balance)],['Valeur totale',money(s.equity)],['P&L réalisé',money(s.realized)],['P&L latent',money(s.unrealized)],['Drawdown max.',(s.max_dd*100).toFixed(2)+' %'],['Capital initial','10 000,00 $']].forEach(([label,value])=>{const box=document.createElement('div');box.className='metric';const title=document.createElement('small');title.textContent=label;const strong=document.createElement('strong');strong.textContent=value;box.append(title,strong);$('metrics').append(box);});
  const q=s.quotes;
  if(q.length){
    const values=q.map(v=>v.mid), lo=Math.min(...values)-1, hi=Math.max(...values)+1;
    const points=values.map((v,i)=>`${40+i/Math.max(1,q.length-1)*840},${210-(v-lo)/(hi-lo)*180}`).join(' ');
    $('chart').innerHTML=`<line x1="40" y1="210" x2="880" y2="210" stroke="#344157"/><polyline points="${points}" fill="none" stroke="#e8c475" stroke-width="2.5"/>`;
    $('price').textContent=money(q.at(-1).mid)+'/oz';
    $('chart-label').textContent=`${stamp(q[0].timestamp)} → ${stamp(q.at(-1).timestamp)} UTC · Min ${money(lo+1)} · Max ${money(hi-1)} · ${q.length} derniers cours · Réception il y a ${Math.max(0,Math.floor(Date.now()/1000-q.at(-1).timestamp))} s`;
  }
  table('positions',['Sens','Onces','Entrée','Stop','Objectif','P&L latent'],s.positions.map(p=>[p.side===1?'Achat':'Vente',p.quantity,money(p.entry),money(p.stop),money(p.target),money(p.unrealized)]));
  table('trades',['Clôture UTC','Sens','Onces','Entrée','Sortie','P&L','Motif'],s.trades.map(p=>[stamp(p.closed),p.side===1?'Achat':'Vente',p.quantity,money(p.entry),money(p.exit),money(p.pnl),p.reason]));
  table('decisions',['UTC','Signal','Décision','Paramètres archivés'],s.decisions.map(d=>[stamp(d.timestamp),{'0':'Attendre','1':'Achat','-1':'Vente'}[d.signal],d.reason,d.params]));
  table('events',['UTC','Type','Détail'],s.events.map(e=>[stamp(e.timestamp),e.kind,e.detail]));
}
async function refresh(){try{const r=await fetch('/api/state');if(!r.ok)throw Error('Serveur indisponible');render(await r.json());$('error').textContent='';}catch(e){$('error').textContent='Connexion perdue : '+e.message;}}
document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',async()=>{
  const buttons=document.querySelectorAll('button');buttons.forEach(x=>x.disabled=true);
  try{const r=await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:b.dataset.action,profile:$('profile').value})});const s=await r.json();if(!r.ok)throw Error(s.detail);render(s);$('error').textContent='';}catch(e){$('error').textContent=e.message;}finally{buttons.forEach(x=>x.disabled=false);}
}));
refresh();setInterval(refresh,1500);
