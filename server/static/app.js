const $=(s,e=document)=>e.querySelector(s),app=$('#app'),modal=$('#modal');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const inr=n=>'₹'+Number(n||0).toLocaleString('en-IN',{maximumFractionDigits:0});
const tok=()=>localStorage.getItem('cl_token'),user=()=>JSON.parse(localStorage.getItem('cl_user')||'null');
async function api(path,o={}){
  const r=await fetch('/api'+path,{method:o.method||'GET',headers:{'Content-Type':'application/json',...(tok()&&{Authorization:'Bearer '+tok()})},body:o.body&&JSON.stringify(o.body)});
  if(r.status===401&&tok()&&!path.startsWith('/auth')){logout();throw new Error('Session expired')}
  const d=r.status===204?{}:await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(d.error||'Something went wrong');return d;
}
function toast(m){const t=document.createElement('div');t.className='toast';t.textContent=m;document.body.append(t);setTimeout(()=>t.remove(),2200)}
function logout(){localStorage.clear();location.hash='#/login'}

/* resource config drives every list page + form */
const OPT={category:['Consultation','Pharmacy','Lab','Dental','Hospital','Other'],status:{bills:['unpaid','paid','disputed'],claims:['submitted','approved','rejected','paid'],appointments:['scheduled','completed','cancelled']}};
const RES={
 bills:{title:'Bills',sub:'Every medical expense in one place.',cols:['date','provider','category','amount','status'],f:[['provider','Provider'],['category','Category','select'],['amount','Amount (₹)','number'],['date','Date','date'],['status','Status','select'],['notes','Notes']]},
 claims:{title:'Insurance claims',sub:'Follow what you filed and what you got back.',cols:['bill','insurer','claimed','approved','status'],f:[['bill_id','Bill','bill'],['insurer','Insurer'],['claimed','Claimed (₹)','number'],['approved','Approved (₹)','number'],['status','Status','select'],['filed_on','Filed on','date']]},
 prescriptions:{title:'Prescriptions',sub:'Doses, costs and refill dates.',cols:['name','dosage','frequency','cost','refill_on'],f:[['name','Medicine'],['dosage','Dosage'],['frequency','How often'],['cost','Cost per refill (₹)','number'],['refill_on','Next refill','date']]},
 appointments:{title:'Appointments',sub:'Visits you have booked and what they cost.',cols:['when_at','doctor','kind','fee','status'],f:[['doctor','Doctor'],['kind','Type of visit'],['when_at','Date and time','datetime-local'],['fee','Fee (₹)','number'],['status','Status','select']]}};
const LBL={when_at:'When',refill_on:'Next refill',bill:'Bill',filed_on:'Filed on'};
const MONEY=['amount','claimed','approved','cost','fee'];
const cell=(k,v)=>v==null||v===''?'<span style="color:var(--mute)">-</span>':MONEY.includes(k)?inr(v):k==='status'?`<span class="badge ${esc(v)}">${esc(v)}</span>`:k==='when_at'?esc(String(v).replace('T',' ')):esc(v);

/* shell */
const PAGES=[['dashboard','Overview'],['bills','Bills'],['claims','Claims'],['prescriptions','Medicines'],['appointments','Visits'],['budget','Budget']];
function shell(active,body){
  const u=user(),pages=u.role==='admin'?[...PAGES,['admin','Admin']]:PAGES;
  app.innerHTML=`<nav class="nav"><a class="logo" href="#/dashboard">Care<em>Ledger</em></a><div class="nav-scroll">${pages.map(([k,n])=>`<a class="l ${k===active?'on':''}" href="#/${k}">${n}</a>`).join('')}</div><button class="btn sm ghost" id="out">Sign out</button></nav><main class="wrap">${body}</main>`;
  $('#out').onclick=logout;
}

/* landing + auth */
const topnav=`<nav class="nav"><a class="logo" href="#/">Care<em>Ledger</em></a><a class="l hide" href="#/">Features</a><a class="l" href="#/login">Sign in</a><a class="btn sm" href="#/register">Get started</a></nav>`;
function landing(){
  app.innerHTML=topnav+`<section class="hero"><div class="grid-bg"></div><div class="arc"></div>
  <h1>Take charge of what your <em>health</em> costs</h1>
  <p><b>CareLedger</b> keeps your medical bills, insurance claims, prescriptions and appointments together, so you always know what you spent, what you got back and what is due next.</p>
  <a class="btn solid" href="#/register">Create free account</a></section>
  <section class="features"><div class="card"><h3>Bills and budgets</h3><p>Log every expense and watch your monthly health budget in real time.</p></div><div class="card"><h3>Claim tracking</h3><p>See which claims are pending, approved or rejected, and how much you recovered.</p></div><div class="card"><h3>Refill reminders</h3><p>Know which medicines run out this week before the pharmacy does.</p></div></section>`;
}
function authPage(mode){
  const reg=mode==='register';
  app.innerHTML=topnav+`<section class="auth"><div class="grid-bg"></div><form id="f"><h2>${reg?'Create your account':'Welcome back'}</h2><p class="hint">${reg?'Start tracking your health spending.':'Sign in to see your dashboard.'}</p>
  ${reg?'<label for="n">Full name</label><input id="n" required autocomplete="name">':''}<label for="e">Email</label><input id="e" type="email" required autocomplete="email"><label for="p">Password</label><input id="p" type="password" required minlength="${reg?8:1}" autocomplete="${reg?'new-password':'current-password'}">
  <div class="err" id="err" role="alert"></div><button class="btn solid">${reg?'Create account':'Sign in'}</button>
  ${reg?'':'<button type="button" class="btn ghost" id="demo">Try the demo account</button>'}</form></section>`;
  const go=async(email,password,name)=>{try{const d=await api('/auth/'+mode,{method:'POST',body:{name,email,password}});localStorage.setItem('cl_token',d.token);localStorage.setItem('cl_user',JSON.stringify(d.user));location.hash='#/dashboard'}catch(e){$('#err').textContent=e.message}};
  $('#f').onsubmit=e=>{e.preventDefault();go($('#e').value,$('#p').value,reg?$('#n').value:undefined)};
  if(!reg)$('#demo').onclick=()=>go('demo@careledger.dev','demo1234');
}

/* dashboard */
async function dashboard(){
  shell('dashboard','<p class="empty">Loading…</p>');
  const d=await api('/dashboard'),max=Math.max(...d.by_category.map(c=>c.total),1),tmax=Math.max(...d.trend.map(t=>t.total),1),pct=d.monthly_limit?Math.min(100,d.month_spend/d.monthly_limit*100):0;
  const li=(a,f)=>a.length?`<ul class="list">${a.map(f).join('')}</ul>`:'<p class="empty">Nothing coming up.</p>';
  $('.wrap').innerHTML=`<div class="page-head"><div><h2>Hello, ${esc(user().name.split(' ')[0])}</h2><p class="hint">Here is where your health spending stands.</p></div><a class="btn" href="#/bills">Add a bill</a></div>
  <div class="stats"><div class="panel stat"><small>Spent this month</small><b>${inr(d.month_spend)}</b></div><div class="panel stat"><small>Unpaid bills</small><b>${inr(d.outstanding)}</b></div><div class="panel stat"><small>Recovered from insurance</small><b class="lime">${inr(d.recovered)}</b></div><div class="panel stat"><small>Claims waiting</small><b>${d.pending_claims}</b></div></div>
  <div class="cols"><div class="panel"><h3>Monthly budget</h3><div class="meter ${pct>=100?'over':''}"><i style="width:${pct}%"></i></div><p class="hint">${d.monthly_limit?`${inr(d.month_spend)} of ${inr(d.monthly_limit)} used`:'No budget set yet. <a href="#/budget" style="color:var(--lime)">Set one</a>'}</p>
  <h3 style="margin-top:18px">This month by category</h3>${d.by_category.map(c=>`<div class="bar-row"><span>${esc(c.category)}</span><i style="width:${c.total/max*100}%"></i><span>${inr(c.total)}</span></div>`).join('')||'<p class="empty">No bills this month.</p>'}</div>
  <div class="panel"><h3>Last six months</h3><div class="trend">${d.trend.map(t=>`<div><i style="height:${t.total/tmax*100}%" title="${inr(t.total)}"></i>${t.month.slice(5)}</div>`).join('')}</div></div></div>
  <div class="cols"><div class="panel"><h3>Upcoming visits</h3>${li(d.appointments,a=>`<li>${esc(a.doctor)} <span>${esc(a.when_at.replace('T',' '))}</span></li>`)}</div><div class="panel"><h3>Refills due this week</h3>${li(d.refills,r=>`<li>${esc(r.name)} <span>${esc(r.refill_on)}</span></li>`)}</div></div>`;
}

/* generic list page */
async function listPage(key){
  const R=RES[key];shell(key,'<p class="empty">Loading…</p>');
  const rows=await api('/'+key);
  const draw=q=>{const v=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q));
    $('#tb').innerHTML=v.length?v.map(r=>`<tr>${R.cols.map(c=>`<td>${cell(c,r[c])}</td>`).join('')}<td class="act"><button class="btn sm ghost" data-e="${r.id}">Edit</button><button class="btn sm del" data-d="${r.id}">Delete</button></td></tr>`).join(''):`<tr><td colspan="9" class="empty">${rows.length?'No matches.':'Nothing here yet. Add your first one.'}</td></tr>`};
  $('.wrap').innerHTML=`<div class="page-head"><div><h2>${R.title}</h2><p class="hint">${R.sub}</p></div><div style="display:flex;gap:8px">${key==='bills'?'<button class="btn ghost" id="csv">Export CSV</button>':''}<button class="btn solid" id="add">Add new</button></div></div>
  <div class="tools"><input id="q" placeholder="Search" aria-label="Search"></div><div class="tablebox"><table><thead><tr>${R.cols.map(c=>`<th>${LBL[c]||c.replace('_',' ').replace(/^./,x=>x.toUpperCase())}</th>`).join('')}<th></th></tr></thead><tbody id="tb"></tbody></table></div>`;
  draw('');$('#q').oninput=e=>draw(e.target.value.toLowerCase());$('#add').onclick=()=>form(key,{});
  $('#tb').onclick=async e=>{const b=e.target.closest('button');if(!b)return;
    if(b.dataset.e)form(key,rows.find(r=>r.id==b.dataset.e));
    if(b.dataset.d&&confirm('Delete this entry?')){await api(`/${key}/${b.dataset.d}`,{method:'DELETE'});toast('Deleted');listPage(key)}};
  if(key==='bills')$('#csv').onclick=async()=>{const r=await fetch('/api/bills/export.csv',{headers:{Authorization:'Bearer '+tok()}}),a=document.createElement('a');a.href=URL.createObjectURL(await r.blob());a.download='bills.csv';a.click()};
}
async function form(key,rec){
  const R=RES[key],bills=key==='claims'?await api('/bills'):[];
  const inp=([n,l,t])=>{const v=rec[n]??'';let h;
    if(t==='select')h=`<select id="f_${n}">${(n==='category'?OPT.category:OPT.status[key]).map(o=>`<option ${o===v||(!v&&o===OPT.status[key]?.[0]&&n==='status')?'selected':''}>${o}</option>`).join('')}</select>`;
    else if(t==='bill')h=`<select id="f_${n}">${bills.map(b=>`<option value="${b.id}" ${b.id==v?'selected':''}>${esc(b.provider)} - ${inr(b.amount)} (${esc(b.date)})</option>`).join('')}</select>`;
    else h=`<input id="f_${n}" type="${t||'text'}" value="${esc(v)}" ${t==='number'?'min="0" step="any"':''}>`;
    return `<label for="f_${n}">${l}</label>${h}`};
  modal.innerHTML=`<form id="mf"><h2 style="font:400 30px var(--serif)">${rec.id?'Edit':'Add'} ${R.title.toLowerCase().replace(/s$/,'')}</h2>${R.f.map(inp).join('')}<div class="err" id="err" role="alert"></div><button class="btn solid">Save</button><button type="button" class="btn ghost" id="x">Cancel</button></form>`;
  modal.showModal();$('#x').onclick=()=>modal.close();
  $('#mf').onsubmit=async e=>{e.preventDefault();const body={};R.f.forEach(([n])=>body[n]=$('#f_'+n).value);
    try{await api(rec.id?`/${key}/${rec.id}`:'/'+key,{method:rec.id?'PUT':'POST',body});modal.close();toast('Saved');listPage(key)}catch(er){$('#err').textContent=er.message}};
}

/* budget + admin */
async function budget(){
  shell('budget','');const [b,d]=await Promise.all([api('/budget'),api('/dashboard')]);
  $('.wrap').innerHTML=`<div class="page-head"><div><h2>Monthly budget</h2><p class="hint">Set a limit for health spending and we will track it for you.</p></div></div><div class="cols"><form class="panel" id="bf"><label for="lim">Monthly limit (₹)</label><input id="lim" type="number" min="0" step="any" value="${b.monthly_limit}"><div class="err" id="err"></div><button class="btn solid">Save budget</button></form>
  <div class="panel"><h3>This month</h3><p class="stat"><b>${inr(d.month_spend)}</b></p><p class="hint">${b.monthly_limit?`${inr(Math.max(b.monthly_limit-d.month_spend,0))} left of ${inr(b.monthly_limit)}`:'No limit set'}</p></div></div>`;
  $('#bf').onsubmit=async e=>{e.preventDefault();try{await api('/budget',{method:'PUT',body:{monthly_limit:$('#lim').value}});toast('Budget saved');budget()}catch(er){$('#err').textContent=er.message}};
}
async function admin(){
  shell('admin','');const d=await api('/admin/stats');
  $('.wrap').innerHTML=`<div class="page-head"><div><h2>Admin</h2><p class="hint">${d.users.length} accounts, ${inr(d.total_spend)} tracked in total.</p></div></div><div class="tablebox"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Bills</th><th>Spend</th><th>Joined</th></tr></thead><tbody>${d.users.map(u=>`<tr><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>${esc(u.role)}</td><td>${u.bills}</td><td>${inr(u.spend)}</td><td>${esc(u.created_at.slice(0,10))}</td></tr>`).join('')}</tbody></table></div>`;
}

/* router */
async function route(){
  const p=(location.hash.replace(/^#\/?/,'')||'');
  if(!p)return landing();
  if(p==='login'||p==='register')return tok()?(location.hash='#/dashboard'):authPage(p);
  if(!tok())return(location.hash='#/login');
  try{
    if(p==='dashboard')await dashboard();else if(RES[p])await listPage(p);else if(p==='budget')await budget();else if(p==='admin'&&user()?.role==='admin')await admin();else location.hash='#/dashboard';
  }catch(e){if(tok())toast(e.message)}
}
addEventListener('hashchange',route);route();
