document.addEventListener('DOMContentLoaded', () => {
  // ---------- Geolocation ----------
  const locBtn  = document.querySelector('[data-loc-for="location"]');
  const locInp  = document.querySelector('input[name="location"]');
  const mapLink = document.getElementById('mapLink');

  function setBusy(el, on) {
    if (!el) return;
    el.disabled = !!on;
    el.dataset.busy = on ? '1' : '0';
  }

  function setMapLink(lat, lon) {
    if (!mapLink) return;
    mapLink.href = `https://www.google.com/maps?q=${lat},${lon}`;
    mapLink.target = '_blank';
    mapLink.rel = 'noopener';
    mapLink.style.display = 'inline-block';
  }

  if (locBtn && locInp) {
    locBtn.addEventListener('click', () => {
      if (!navigator.geolocation) { alert('Geolocation not supported'); return; }
      setBusy(locBtn, true);
      navigator.geolocation.getCurrentPosition(
        pos => {
          const lat = pos.coords.latitude.toFixed(6);
          const lon = pos.coords.longitude.toFixed(6);
          locInp.value = `${lat}, ${lon}`;
          setMapLink(lat, lon);
          setBusy(locBtn, false);
        },
        () => { alert('Unable to get location'); setBusy(locBtn, false); },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  }

  // ---------- Save + Finalize ----------
  const form = document.getElementById('cForm');
  if (!form) return;

  const SAVE_URL     = form.dataset.saveUrl     || window.CLIENT_SAVE_URL   || '/clients/api/save/';
  const FINALIZE_URL = form.dataset.finalizeUrl || window.FINALIZE_URL      || '/clients/api/finalize/';
  const REDIRECT_TO  = form.dataset.redirectTo  || '/archives/';

  const weeklyIdEl = document.getElementById('weeklyPlanId');
  const dailyIdEl  = document.getElementById('dailyVisitId');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const csrf = document.querySelector('#logoutForm input[name=csrfmiddlewaretoken]')?.value || '';
    const submitBtn = form.querySelector('[type="submit"]');
    setBusy(submitBtn, true);

    // 1) Save client
    let clientId = null;
    try {
      const fd = new FormData(form);
      const res = await fetch(SAVE_URL, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf },
        body: fd
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.ok) throw new Error(data?.msg || 'Save client failed');
      clientId = data.id || data.pk || data.client_id;
    } catch (err) {
      alert(err.message || 'Save failed');
      setBusy(submitBtn, false);
      return;
    }

    // 2) Finalize (archive client + weekly + daily) — لو الـIDs موجودة
    const weeklyId = weeklyIdEl?.value || form.querySelector('input[name="weekly_plan_id"]')?.value;
    const dailyId  = dailyIdEl?.value  || form.querySelector('input[name="daily_visit_id"]')?.value;

    if (clientId && weeklyId && dailyId) {
      try {
        const body = new URLSearchParams({
          client_id: String(clientId),
          weekly_plan_id: String(weeklyId),
          daily_visit_id: String(dailyId)
        });
        await fetch(FINALIZE_URL, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf, 'Accept': 'application/json' },
          body
        });
      } catch {
        // حتى لو فشل الـfinalize، ما نعطلّش المستخدم — لكن يفضل تراجِع اللوج
      }
    }

    // 3) Redirect للأرشيف (المهمّة اتقفلت واختفت من الصفحات التلاتة)
    window.location.href = REDIRECT_TO;
  });
});
