// static/assets/js/weekly.js
document.addEventListener('DOMContentLoaded', () => {
  // -------- Toggle "Other Objective" required ----------
  const objectiveSel = document.getElementById('visitObjective');
  const otherInput   = document.getElementById('otherObjective');

  function syncOtherRequired() {
    const needOther = objectiveSel && objectiveSel.value === 'Other';
    if (otherInput) {
      otherInput.required = !!needOther;
      otherInput.disabled = !needOther;
      if (!needOther) otherInput.value = '';
    }
  }
  if (objectiveSel) {
    syncOtherRequired();
    objectiveSel.addEventListener('change', syncOtherRequired);
  }

  // -------- Current Location -> write to entity_address ----------
  const geoBtn  = document.querySelector('[data-loc-for="entity_address"]');
  const addrInp = document.querySelector('input[name="entity_address"]');
  const mapLink = document.getElementById('mapLink');

  if (geoBtn && addrInp) {
    geoBtn.addEventListener('click', () => {
      if (!navigator.geolocation) { alert('Geolocation not supported'); return; }
      geoBtn.disabled = true;
      navigator.geolocation.getCurrentPosition(
        pos => {
          const lat = pos.coords.latitude.toFixed(6);
          const lon = pos.coords.longitude.toFixed(6);
          // اكتب الإحداثيات في خانة العنوان (بنفس الخانة المستخدمة في الموديل)
          const coords = `${lat}, ${lon}`;
          // لو العنوان مكتوب، هنضيف الإحداثيات في الآخر بين أقواس
          if (addrInp.value && !addrInp.value.includes(coords)) {
            addrInp.value = `${addrInp.value} (${coords})`;
          } else {
            addrInp.value = coords;
          }
          if (mapLink) {
            mapLink.href = `https://www.google.com/maps?q=${lat},${lon}`;
            mapLink.style.display = 'inline-block';
          }
          geoBtn.disabled = false;
        },
        err => {
          alert('Unable to get location');
          geoBtn.disabled = false;
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  }

  // -------- احمِ الأزرار من الدبل-كليك (اختياري خفيف) ----------
  document.body.addEventListener('submit', (e) => {
    const btn = e.target.querySelector('button[type="submit"]');
    if (btn) {
      btn.disabled = true;
      setTimeout(() => { btn.disabled = false; }, 2000);
    }
  }, true);
});
