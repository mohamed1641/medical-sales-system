(function () {
  const dataEl = document.getElementById('dashdata');
  if (!dataEl) return;
  const dash = JSON.parse(dataEl.textContent || '{}');

  // ===== KPIs =====
  const k = dash.kpis || {};
  const s = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = (v ?? '0'); };
  s('k_total', k.total);
  s('k_approved', k.approved);
  s('k_deals', k.deals);
  s('k_reps', k.reps);

  s('conv', (k.conversion || 0) + '%');
  s('clientsCount', k.clients);
  s('upcoming', k.upcoming);

  const repTotal = document.getElementById('repTotal');
  if (repTotal) repTotal.textContent = (k.by_rep_total || 0) + ' visits';

  // ===== Bars: Visits by Rep =====
  (function renderBars(){
    const wrap = document.getElementById('bars');
    if (!wrap) return;
    wrap.innerHTML = '';
    const rows = dash.by_rep || [];
    const max = Math.max(1, ...rows.map(r => r.count||0));
    rows.forEach(r => {
      const row = document.createElement('div');
      row.className = 'barrow';
      const lbl = document.createElement('span');
      lbl.className = 'barlbl';
      lbl.textContent = r.label || '—';
      const bar = document.createElement('div');
      bar.className = 'bar';
      bar.style.width = ((r.count || 0) / max * 100).toFixed(0) + '%';
      bar.setAttribute('title', r.count || 0);
      row.appendChild(lbl);
      row.appendChild(bar);
      wrap.appendChild(row);
    });
  })();

  // ===== Line chart: Monthly Trend (canvas#lineChart) =====
  (function renderLine(){
    const cv = document.getElementById('lineChart');
    if (!cv) return;
    const ctx = cv.getContext('2d');
    const DPR = window.devicePixelRatio || 1;
    const w = cv.clientWidth * DPR, h = cv.clientHeight * DPR;
    cv.width = w; cv.height = h;

    const labels = (dash.trend && dash.trend.labels) || [];
    const visits = (dash.trend && dash.trend.visits) || [];
    const deals  = (dash.trend && dash.trend.deals)  || [];

    const pad = 32 * DPR;
    const plotW = w - pad*2, plotH = h - pad*2;
    const maxY = Math.max(1, ...visits, ...deals);
    const toXY = (i, v, n) => {
      const x = pad + (plotW * (i / Math.max(1, n-1)));
      const y = pad + (plotH * (1 - (v / maxY)));
      return [x, y];
    };

    const color1 = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#6c63ff';
    const color2 = getComputedStyle(document.documentElement).getPropertyValue('--accent-3').trim() || '#00d18f';

    // bg
    ctx.clearRect(0,0,w,h);
    ctx.font = (12*DPR)+'px system-ui,Segoe UI,Arial';
    ctx.fillStyle = 'rgba(255,255,255,0.06)';
    // grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1*DPR;
    ctx.beginPath();
    for (let i=0;i<=5;i++){
      const y = pad + (plotH * i/5);
      ctx.moveTo(pad, y); ctx.lineTo(pad+plotW, y);
    }
    ctx.stroke();

    // axes
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.beginPath();
    ctx.moveTo(pad, pad); ctx.lineTo(pad, pad+plotH);
    ctx.moveTo(pad, pad+plotH); ctx.lineTo(pad+plotW, pad+plotH);
    ctx.stroke();

    // line helper
    function drawLine(vals, color){
      ctx.beginPath();
      vals.forEach((v,i)=>{
        const [x,y]=toXY(i, v||0, vals.length);
        if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
      });
      ctx.strokeStyle = color; ctx.lineWidth = 2*DPR; ctx.stroke();

      // points
      vals.forEach((v,i)=>{
        const [x,y]=toXY(i, v||0, vals.length);
        ctx.beginPath(); ctx.arc(x,y,2.5*DPR,0,Math.PI*2);
        ctx.fillStyle = color; ctx.fill();
      });
    }
    drawLine(visits, color1);
    drawLine(deals,  color2);
  })();

  // ===== Tables =====
  function fillTable(tid, rows, cols){
    const tb = document.querySelector(`#${tid} tbody`);
    if (!tb) return;
    tb.innerHTML = '';
    (rows||[]).forEach(r=>{
      const tr = document.createElement('tr');
      cols.forEach(c=>{
        const td = document.createElement('td');
        td.textContent = r[c] != null && r[c] !== '' ? r[c] : '—';
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
  }
  fillTable('t_recent', dash.recent, ['dt','rep','account','doctor','outcome']);
  // upcoming: التاريخ ممكن يبقى Date object stringified من Django
  const upcomingRows = (dash.upcoming||[]).map(r=>{
    const d = (''+r.date).slice(0,10);
    return {date:d, rep:r.rep, plan:r.plan, obj:r.obj};
  });
  fillTable('t_next', upcomingRows, ['date','rep','plan','obj']);

  // ===== Range selector -> reload with query =====
  const sel = document.getElementById('range');
  if (sel) {
    sel.addEventListener('change', ()=>{
      const v = sel.value;
      const url = new URL(location.href);
      url.searchParams.set('range', v);
      location.href = url.toString();
    });
  }
})();
