// assets/js/archives.js
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('syncBtn');
  if (!btn) return;

  // هنستخدم CSRF من فورم اللوجآوت المخفي
  const csrf = document.querySelector('#logoutForm input[name=csrfmiddlewaretoken]')?.value || '';

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    const prev = btn.textContent;
    btn.textContent = 'Syncing…';

    try {
      const res = await fetch(window.location.pathname + 'sync/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf }
      });
      const data = await res.json();
      if (data.ok) {
        location.reload();
      } else {
        alert(data.msg || 'Sync failed');
        btn.disabled = false; btn.textContent = prev;
      }
    } catch (e) {
      alert('Network error during sync');
      btn.disabled = false; btn.textContent = prev;
    }
  });
});
