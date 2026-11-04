/* AT Advisory: interacciones de la web, sin dependencias.
   Todo es una mejora progresiva: sin JavaScript la página se lee entera y el formulario sigue funcionando. */
(function () {
  'use strict';

  // ── Tarjeta de la portada: pestañas y simulación (idle → running → done) ──
  document.querySelectorAll('.demo').forEach(function (box) {
    var timer = 0;
    var tabs = box.querySelectorAll('.demo-tab');
    var run = box.querySelector('.demo-run');
    var reset = box.querySelector('.demo-reset');

    tabs.forEach(function (btn) {
      btn.addEventListener('click', function () {
        clearTimeout(timer);
        box.setAttribute('data-instant', '');          // cambiar de ejemplo es instantáneo, sin fundidos
        box.setAttribute('data-active', btn.getAttribute('data-tab'));
        box.setAttribute('data-state', 'idle');
        tabs.forEach(function (b) { b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'); });
        void box.offsetWidth;                          // aplica el cambio sin transiciones…
        box.removeAttribute('data-instant');           // …y las vuelve a activar para «Ver qué hace la IA»
      });
    });

    if (run) run.addEventListener('click', function () {
      var hadFocus = document.activeElement === run;
      clearTimeout(timer);
      box.setAttribute('data-state', 'running');
      timer = setTimeout(function () {
        box.setAttribute('data-state', 'done');
        if (hadFocus && reset) reset.focus();
      }, 1200);
    });

    if (reset) reset.addEventListener('click', function () {
      var hadFocus = document.activeElement === reset;
      clearTimeout(timer);
      box.setAttribute('data-state', 'idle');
      if (hadFocus && run) run.focus();
    });
  });

  // ── Aparición de bloques al llegar a ellos ──
  if (document.querySelector('[data-reveal]')) {
    var check = function () {
      var limit = window.innerHeight * 0.92;
      document.querySelectorAll('[data-reveal]:not([data-in])').forEach(function (el) {
        if (el.getBoundingClientRect().top < limit) {
          var sibs = Array.prototype.filter.call(el.parentElement.children, function (c) { return c.hasAttribute('data-reveal'); });
          el.style.transitionDelay = Math.max(0, sibs.indexOf(el)) * 90 + 'ms';
          el.setAttribute('data-in', '');
        }
      });
    };
    var queued = false;
    var onScroll = function () {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; check(); });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    document.documentElement.classList.add('reveal-ready');
    requestAnimationFrame(check);
    setTimeout(check, 300);
  }

  // ── Botón «Copiar correo» ──
  document.querySelectorAll('[data-copy]').forEach(function (btn) {
    var label = btn.textContent;
    var copied = function () {
      btn.textContent = btn.getAttribute('data-done') || label;
      btn.setAttribute('data-state', 'done');
      setTimeout(function () { btn.textContent = label; btn.removeAttribute('data-state'); }, 2000);
    };
    var fallback = function (text) {
      var area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'absolute';
      area.style.left = '-9999px';
      document.body.appendChild(area);
      area.select();
      try { if (document.execCommand('copy')) copied(); } catch (e) { /* el enlace mailto sigue disponible */ }
      document.body.removeChild(area);
    };
    btn.addEventListener('click', function () {
      var text = btn.getAttribute('data-copy');
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(copied, function () { fallback(text); });
      } else {
        fallback(text);
      }
    });
  });

  // ── Formulario de contacto ──
  var form = document.querySelector('form.contact-form');
  if (form) form.addEventListener('submit', function (event) {
    event.preventDefault();
    var data = new FormData(form);
    var value = function (name) { return (data.get(name) || '').toString(); };

    // Sin clave de Web3Forms: abre el correo del visitante con el mensaje ya redactado.
    if (!form.getAttribute('data-key')) {
      var subject = 'AT Advisory enquiry — ' + (value('org') || value('name'));
      var body = ['Name: ' + value('name'), 'Email: ' + value('email'), 'Business: ' + value('org'), '', value('message')].join('\n');
      window.location.href = 'mailto:' + form.getAttribute('data-email') +
        '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
      return;
    }

    if (value('botcheck')) return;  // trampa para bots
    var status = form.querySelector('.form-status');
    var button = form.querySelector('[type="submit"]');
    var show = function (state) {
      status.hidden = false;
      status.setAttribute('data-state', state);
      status.textContent = form.getAttribute('data-' + state);
    };
    var payload = {};
    data.forEach(function (v, k) { payload[k] = v; });

    show('sending');
    button.disabled = true;
    fetch(form.action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (res) {
        return res.json().then(function (json) {
          if (!res.ok || !json.success) throw new Error(json.message || res.status);
        });
      })
      .then(function () { form.reset(); show('success'); })
      .catch(function () { show('error'); })
      .then(function () { button.disabled = false; });
  });
})();
