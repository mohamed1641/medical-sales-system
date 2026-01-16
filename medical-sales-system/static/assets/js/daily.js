// Sync button (زي ما هو)
const syncBtn = document.getElementById('syncBtn');
if (syncBtn) {
  syncBtn.addEventListener('click', () => {
    const params = new URLSearchParams(new FormData(document.getElementById('listForm')));
    window.location.href = (window.SYNC_URL || '/visits/sync/') + '?' + params.toString();
  });
}

// ----- Connect Save to API -----
const vForm = document.getElementById('vForm');
if (vForm) {
  vForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const csrf = document.querySelector('#logoutForm input[name=csrfmiddlewaretoken]')?.value || '';
    try {
      const res = await fetch('/visits/api/save/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf },
        body: new FormData(vForm)
      });
      const data = await res.json().catch(()=>null);
      if (!res.ok || !data?.ok) {
        alert(data?.msg || 'Save failed');
        return;
      }
      vForm.reset();
      location.reload(); // خليها Reload بسيط لعرض الصف في الجدول
    } catch (err) {
      alert('Network error');
    }
  });
}
// ----- Edit: fill form -----
(function () {
  const tbl = document.getElementById('tbl');
  const vForm = document.getElementById('vForm');
  if (!tbl || !vForm) return;

  const setVal = (sel, val) => {
    const el = vForm.querySelector(sel);
    if (!el) return;
    el.value = (val ?? '');
  };

  tbl.addEventListener('click', (e) => {
    const btn = e.target.closest('.edit-btn');
    if (!btn) return;

    setVal('input[name="id"]', btn.dataset.id || '');
    setVal('input[name="visited_account"]', btn.dataset.visited_account || '');
    setVal('input[name="actual_datetime"]', btn.dataset.actual_datetime || '');
    setVal('select[name="time_shift"]', btn.dataset.timeShift || btn.dataset.time_shift || '');
    setVal('input[name="doctor_name"]', btn.dataset.doctorName || btn.dataset.doctor_name || '');
    setVal('input[name="phone"]', btn.dataset.phone || '');
    setVal('select[name="visit_outcome"]', btn.dataset.visitOutcome || btn.dataset.visit_outcome || '');
    setVal('input[name="additional_outcome"]', btn.dataset.additionalOutcome || btn.dataset.additional_outcome || '');
    setVal('select[name="visit_status"]', btn.dataset.visitStatus || btn.dataset.visit_status || '');
    setVal('select[name="weekly_plan_id"]', btn.dataset.weeklyPlanId || btn.dataset.weekly_plan_id || '');
    setVal('input[name="client_doctor"]', btn.dataset.clientDoctor || btn.dataset.client_doctor || '');

    const repSel = vForm.querySelector('select[name="rep"]');
    if (repSel && btn.dataset.rep) repSel.value = btn.dataset.rep;

    vForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
})();

// ----- Delete: soft delete -----
(function () {
  const tbl = document.getElementById('tbl');
  const csrf = document.querySelector('#logoutForm input[name=csrfmiddlewaretoken]')?.value || '';
  if (!tbl || !csrf) return;

  tbl.addEventListener('click', async (e) => {
    const del = e.target.closest('.del-btn');
    if (!del) return;
    if (!confirm('Delete this visit?')) return;

    try {
      const res = await fetch(`/visits/api/delete/${del.dataset.id}/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf }
      });
      const j = await res.json().catch(() => ({}));
      if (res.ok && (j.ok || j.soft_deleted)) location.reload();
      else alert('Delete failed');
    } catch (err) {
      alert('Network error');
    }
  });
})();
// ربط week_number من اختيار الويكلى
const weeklySel = document.getElementById('weeklySelect');
const weekHidden = document.getElementById('weekNumberHidden');
if (weeklySel && weekHidden) {
  const syncWeek = () => {
    const opt = weeklySel.options[weeklySel.selectedIndex];
    const wk = opt ? opt.getAttribute('data-week') : '';
    weekHidden.value = wk || '';
  };
  weeklySel.addEventListener('change', syncWeek);
  syncWeek();
}
