// app.js — minimal JS (keep project lightweight)
// -------------------------------------------------
// 1) Toggle 'Other Objective' field in Weekly form
// 2) Current Location button (Weekly & Clients)
// 3) Optional: highlight current nav link

(function(){
  function $(sel, ctx){ return (ctx||document).querySelector(sel); }
  function on(el, ev, fn){ el && el.addEventListener(ev, fn); }

  // NAV highlight (no style changes)
  (function highlightActiveNav(){
    var links = document.querySelectorAll('nav.tabs a');
    var loc = window.location.pathname.replace(/\/$/, '');
    links.forEach(function(a){
      var href = a.getAttribute('href').replace(/\/$/, '');
      if(href && href === loc){ a.classList.add('active'); }
    });
  })();

  // WEEKLY: toggle 'Other' objective
  (function initWeekly(){
    var sel = document.querySelector('form#wkForm select[name="visit_objective"]');
    var other = document.querySelector('form#wkForm input[name="other_objective"]');
    if(!sel || !other) return;
    function sync(){
      var show = (sel.value || '').toLowerCase() === 'other';
      other.closest('.form-row')?.classList.toggle('hidden', !show);
    }
    on(sel, 'change', sync);
    sync();
  })();

  // GEO: for any button with [data-geolocate] fill nearest address into target input
  (function initGeolocate(){
    function reverseGeocode(lat, lng){
      // Keep it minimal: use open Nominatim
      return fetch('https://nominatim.openstreetmap.org/reverse?format=json&lat='+lat+'&lon='+lng)
        .then(function(r){ return r.json(); })
        .then(function(j){ return j.display_name || (lat+', '+lng); })
        .catch(function(){ return lat+', '+lng; });
    }
    document.querySelectorAll('[data-geolocate]').forEach(function(btn){
      on(btn, 'click', function(e){
        e.preventDefault();
        var targetSel = btn.getAttribute('data-target');
        var out = document.querySelector(targetSel);
        if(!navigator.geolocation || !out) return;
        btn.disabled = true;
        navigator.geolocation.getCurrentPosition(function(pos){
          var lat = pos.coords.latitude, lng = pos.coords.longitude;
          reverseGeocode(lat,lng).then(function(addr){
            out.value = addr;
            btn.disabled = false;
          });
        }, function(){
          btn.disabled = false;
        });
      });
    });
  })();

  // Note: Search & Export CSV are server-side (GET & ?export=csv). No JS required.
})();