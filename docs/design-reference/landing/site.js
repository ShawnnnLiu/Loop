/* Admissions Copilot — shared site behavior
   - EN | 中文 toggle: swaps every [data-zh] element's content, persists in localStorage
   - keeps the EN copy as the inline default (no-JS safe), caches it on load
*/
(function () {
  var KEY = 'ac_lang';
  var enCache = new Map();
  var zhEls = [];

  function collect() {
    zhEls = Array.prototype.slice.call(document.querySelectorAll('[data-zh]'));
    zhEls.forEach(function (el) { enCache.set(el, el.innerHTML); });
  }

  function apply(lang) {
    zhEls.forEach(function (el) {
      el.innerHTML = (lang === 'zh') ? el.getAttribute('data-zh') : enCache.get(el);
    });
    document.documentElement.lang = (lang === 'zh') ? 'zh-Hans' : 'en';
    document.body.classList.toggle('lang-zh', lang === 'zh');
    // toggle button state
    document.querySelectorAll('.lang-pill button').forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-lang') === lang);
    });
    try { localStorage.setItem(KEY, lang); } catch (e) {}
  }

  function init() {
    collect();
    var saved = 'en';
    try { saved = localStorage.getItem(KEY) || 'en'; } catch (e) {}
    apply(saved);

    document.querySelectorAll('.lang-pill button').forEach(function (b) {
      b.addEventListener('click', function () { apply(b.getAttribute('data-lang')); });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

/* ----------------------------------------------------------------
   Accent palette picker — recolors the brand accent system.
   Five expert-tuned earthy skins; each carries its own accent family
   AND support roles (success, warning, parent-door), per the brief.
   Persists in localStorage; applied as CSS-var overrides on :root.
   ---------------------------------------------------------------- */
(function () {
  var KEY = 'ac_accent';
  // [0 id, 1 EN, 2 ZH, 3 clay, 4 deep, 5 soft, 6 tint,
  //  7 success, 8 success-soft, 9 warn, 10 warn-soft, 11 parent-door-soft]
  var PALETTES = [
    ['cinnabar',   'Cinnabar',   '朱砂', '#a8453a', '#87352c', '#e7cdc6', '#f1e3dc',
       '#5f7a64', '#e3ebe2', '#c08a3e', '#f6e6cf', '#e3ebe2'],
    ['amber',      'Amber',      '琥珀', '#a87434', '#855a24', '#e7d8c4', '#f1e8db',
       '#5f7a64', '#e3ebe2', '#bd5a39', '#f0ddd0', '#e3ebe2'],
    ['pine',       'Pine',       '苍松', '#46685a', '#355043', '#d0d5cd', '#e5e7e0',
       '#c08a3e', '#f3e7cf', '#bd5a39', '#f0ddd0', '#f3e7cf'],
    ['indigo',     'Ink indigo', '黛青', '#44587a', '#33425e', '#cfd2d5', '#e5e5e4',
       '#5f7a64', '#e3ebe2', '#c08a3e', '#f6e6cf', '#e3ebe2'],
    ['sandalwood', 'Sandalwood', '紫檀', '#76485e', '#5c3349', '#dbcecf', '#ebe3e0',
       '#5f7a64', '#e3ebe2', '#c08a3e', '#f6e6cf', '#e3ebe2']
  ];

  function byId(id) { for (var i=0;i<PALETTES.length;i++){ if (PALETTES[i][0]===id) return PALETTES[i]; } return PALETTES[0]; }

  function apply(id) {
    var p = byId(id);
    var root = document.documentElement.style;
    root.setProperty('--clay', p[3]);
    root.setProperty('--clay-deep', p[4]);
    root.setProperty('--clay-soft', p[5]);
    root.setProperty('--clay-tint', p[6]);
    root.setProperty('--sage', p[7]);
    root.setProperty('--sage-soft', p[8]);
    root.setProperty('--gold', p[9]);
    root.setProperty('--warn-soft', p[10]);
    root.setProperty('--door-parent-soft', p[11]);
    document.querySelectorAll('.accent-sw').forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-accent') === p[0]);
    });
    var dot = document.querySelector('.accent-launch .dot');
    if (dot) dot.style.background = p[3];
    try { localStorage.setItem(KEY, p[0]); } catch (e) {}
  }

  function build() {
    var css = '' +
      '.accent-fab{position:fixed;right:18px;bottom:18px;z-index:80;font-family:var(--sans);}' +
      '.accent-launch{display:flex;align-items:center;gap:8px;cursor:pointer;border:1px solid var(--line-2);' +
        'background:color-mix(in srgb,var(--card) 90%,transparent);backdrop-filter:blur(10px);' +
        'border-radius:999px;padding:8px 13px 8px 10px;box-shadow:var(--shadow-sm);font-size:13px;' +
        'font-weight:600;color:var(--ink-soft);transition:box-shadow .18s,transform .18s;}' +
      '.accent-launch:hover{box-shadow:var(--shadow);transform:translateY(-1px);}' +
      '.accent-launch .dot{width:15px;height:15px;border-radius:50%;background:var(--clay);' +
        'box-shadow:inset 0 0 0 2px rgba(255,255,255,.6);flex:none;}' +
      '.accent-pop{position:absolute;right:0;bottom:calc(100% + 10px);width:212px;background:var(--card);' +
        'border:1px solid var(--line-2);border-radius:14px;box-shadow:var(--shadow-lg);padding:13px;' +
        'opacity:0;visibility:hidden;transform:translateY(6px);transition:opacity .18s,transform .18s,visibility .18s;}' +
      '.accent-fab.open .accent-pop{opacity:1;visibility:visible;transform:translateY(0);}' +
      '.accent-pop .ap-h{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;' +
        'color:var(--muted);margin:0 2px 10px;}' +
      '.accent-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;}' +
      '.accent-sw{position:relative;aspect-ratio:1;border-radius:9px;border:1px solid rgba(22,33,46,.12);' +
        'cursor:pointer;padding:0;transition:transform .14s;}' +
      '.accent-sw:hover{transform:scale(1.08);}' +
      '.accent-sw.on{box-shadow:0 0 0 2px var(--card),0 0 0 4px var(--ink);}' +
      '.accent-sw.on::after{content:"";position:absolute;inset:0;margin:auto;width:7px;height:7px;border-radius:50%;' +
        'background:#fff;box-shadow:0 0 0 1px rgba(0,0,0,.15);}' +
      '.accent-name{font-size:12px;font-weight:600;color:var(--ink-soft);text-align:center;margin-top:11px;min-height:15px;}';
    var style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);

    var fab = document.createElement('div'); fab.className = 'accent-fab';
    var sw = '';
    PALETTES.forEach(function (p) {
      sw += '<button class="accent-sw" data-accent="'+p[0]+'" title="'+p[1]+'" ' +
            'style="background:'+p[3]+'"></button>';
    });
    fab.innerHTML =
      '<div class="accent-pop">' +
        '<p class="ap-h" data-zh="主题色">Accent</p>' +
        '<div class="accent-grid">'+sw+'</div>' +
        '<div class="accent-name"></div>' +
      '</div>' +
      '<div class="accent-launch"><span class="dot"></span><span data-zh="配色">Color</span></div>';
    document.body.appendChild(fab);

    var launch = fab.querySelector('.accent-launch');
    var nameEl = fab.querySelector('.accent-name');
    launch.addEventListener('click', function (e) { e.stopPropagation(); fab.classList.toggle('open'); });
    document.addEventListener('click', function (e) { if (!fab.contains(e.target)) fab.classList.remove('open'); });
    fab.querySelectorAll('.accent-sw').forEach(function (b) {
      var p = byId(b.getAttribute('data-accent'));
      var zh = document.body.classList.contains('lang-zh');
      b.addEventListener('mouseenter', function () { nameEl.textContent = zh ? p[2] : p[1]; });
      b.addEventListener('mouseleave', function () { nameEl.textContent = ''; });
      b.addEventListener('click', function () { apply(b.getAttribute('data-accent')); });
    });

    var saved = 'cinnabar';
    try { var s = localStorage.getItem(KEY); if (s && byId(s)[0] === s) saved = s; } catch (e) {}
    apply(saved);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build);
  } else {
    build();
  }
})();
