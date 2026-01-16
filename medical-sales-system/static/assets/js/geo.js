// static/assets/js/geo.js
(function () {
  async function reverseGeocode(lat, lon) {
    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}`;
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!res.ok) throw new Error('Reverse geocoding failed');
    return res.json();
  }

  function setMapLink(lat, lon) {
    const link = document.querySelector('#mapLink');
    if (link) {
      link.href = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;
      link.style.display = 'inline-block';
    }
  }

  document.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-loc-for]');
    if (!btn) return;

    const fieldName = btn.getAttribute('data-loc-for');
    const input = document.querySelector(`[name="${fieldName}"]`);
    if (!input) return;

    if (!navigator.geolocation) {
      alert('Geolocation not supported in this browser.');
      return;
    }

    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Getting location…';

    navigator.geolocation.getCurrentPosition(async (pos) => {
      const { latitude, longitude } = pos.coords;
      try {
        const data = await reverseGeocode(latitude, longitude);
        const label = data.display_name || `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
        input.value = label;
        setMapLink(latitude, longitude);
      } catch (err) {
        input.value = `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
        setMapLink(latitude, longitude);
      } finally {
        btn.disabled = false;
        btn.textContent = original;
      }
    }, (err) => {
      alert('Could not get location. Please allow location permission.');
      btn.disabled = false;
      btn.textContent = original;
    }, { enableHighAccuracy: true, timeout: 10000 });
  });
})();
