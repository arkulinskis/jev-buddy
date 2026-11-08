/* Smoke test (tools/ui_test.py runs it at 1280 px and at 390 px): every page address opens without errors, is not
   empty and doesn't scroll sideways, signed out (guide chapters, use cases, the playground with a simulated run, the
   open-source picker, the three calculators), then as a new member (save a recipe from the playground, My recipes,
   the recipe page, forking it back into the playground, profile), then as admin (every Admin tab).
   Python/JS errors are caught by ui_test.py from the browser log. Resolves to {ok, log}. */
(async function () {
  const log = [], bad = [];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 20000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  const errs = [];
  window.addEventListener('error', (e) => errs.push(String(e.message || e)));
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function button(re, root) { return $$((root || '') + ' button').find((b) => re.test(b.textContent) && b.offsetParent !== null); }
  async function open(hash, expect, landed) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY && (landed ? landed() : location.hash === hash), hash, 30000);
    await sleep(700);
    const main = $('.ui-main');
    const text = main ? main.innerText.trim() : '';
    const w = document.documentElement.scrollWidth, vw = screen.width <= 500 ? screen.width : window.innerWidth;
    const problems = [];
    if (text.length < 40) problems.push('empty page');
    if (expect && !new RegExp(expect.source, 'i').test(text)) problems.push('missing ' + expect);
    if (w > vw + 1) {
      const wide = $$('body *').filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.right > vw + 1; })
        .slice(0, 3).map((e) => e.tagName.toLowerCase() + '.' + String(e.className).split(' ').slice(0, 2).join('.'));
      problems.push('scrolls sideways (' + w + ' > ' + vw + ') ' + wide.join(' '));
    }
    if (errs.length) problems.push('errors: ' + errs.splice(0).join(' / '));
    if (problems.length) bad.push(hash + ': ' + problems.join('; '));
    log.push((problems.length ? 'BAD  ' : 'ok   ') + hash);
  }
  async function signUp(name, email, password) {
    location.hash = '#auth/signup';
    await until(() => window.UI_READY && $$('.au-card input').length >= 3, 'sign-up form');
    await sleep(400);
    const inputs = $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]');
    type(inputs[0], name); type(inputs[1], email); type(inputs[2], password);
    const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
    button(/Create account/, '.au-card .anvil-role-btn-block').click();
    const end = Date.now() + 30000;
    while (Date.now() < end) {
      if (location.hash.indexOf('#learn') === 0 && window.UI_READY) return true;
      const msg = $('.au-card .anvil-role-msg-error');
      if (msg && msg.offsetParent !== null && msg.textContent.trim()) { log.push('sign-up said: ' + msg.textContent.trim()); return false; }
      await sleep(200);
    }
    log.push('sign-up: still on ' + location.hash);
    return false;
  }
  async function signIn(email, password) {
    location.hash = '#auth';
    await until(() => window.UI_READY && $$('.au-card input[type=password]').length, 'sign-in form');
    await sleep(400);
    type($('.au-card input[type=email]'), email); type($('.au-card input[type=password]'), password);
    button(/Sign in/, '.au-card .anvil-role-btn-block').click();
    await until(() => location.hash.indexOf('#learn') === 0 && window.UI_READY, 'signed in as ' + email, 30000);
  }
  async function signOut() {
    $('.anvil-role-avatar button').click();
    await sleep(300);
    button(/Sign out/, '.ui-menu').click();
    await until(() => {
      const a = $('.anvil-role-avatar button');
      return location.hash === '#landing' && window.UI_READY && (!a || a.offsetParent === null);
    }, 'signed out');
  }
  try {
    // ---- signed out
    await open('#landing', /Ask for a decision/);
    if (!$('.lp-term')) bad.push('#landing: no decision terminal');
    await open('#learn', /Everything a developer needs/);
    await open('#learn/quickstart', /first call/);
    if (!$('.jb-code pre')) bad.push('#learn/quickstart: no code block');
    await open('#learn/self-host', /Laya/);
    await open('#learn/resources', /Sources/);
    await open('#examples', /earns its keep/);
    const chip = button(/Finance/, '.ex-chips');
    if (chip) { chip.click(); await sleep(800); if ($$('.ex-card').length >= 12) bad.push('#examples: the category chip did not filter'); button(/^\s*All\s*$/, '.ex-chips').click(); await sleep(500); }
    await open('#examples/support-inbox', /AI support inbox/);
    if ($$('.jb-ans-card').length < 3) bad.push('#examples/support-inbox: answer cards missing');
    await open('#playground', /Questions \(/);
    button(/^\s*Run\s*$/, '.pg-run').click();
    await until(() => $$('.pg-out .jb-ans-card').length >= 1, 'simulated answers', 15000).catch(() => bad.push('#playground: Run showed no answers'));
    button(/Code/, '.pg-tabs').click(); await sleep(400);
    if (!/requests\.post|fetch\(/.test(($('.pg-out') || {}).innerText || '')) bad.push('#playground: the Code tab is empty');
    await open('#recipes', /Community recipes/);
    await open('#recipes/mine', /Save your own recipes/);
    await open('#opensource', /on your own machine/);
    const hw = button(/NVIDIA GPU/, '.os-chips');
    if (hw) { hw.click(); await sleep(600); if (!$('.os-card.dim')) bad.push('#opensource: the hardware picker did not dim any card'); }
    await open('#opensource/expose', /Putting your server online/);
    await open('#tools/cost', /Jev per month/);
    await open('#tools/cost/40000/230/3', /Jev per month/);
    await open('#tools/confidence', /The maths/);
    button(/^\s*score\s*$/, '.tl-form').click(); await sleep(500);
    if (!/most likely level/.test(($('.ui-main') || {}).innerText || '')) bad.push('#tools/confidence: score maths missing');
    await open('#tools/thresholds', /handled automatically/);
    if (!$('.tl-chart svg rect')) bad.push('#tools/thresholds: no histogram');
    await open('#auth', /Sign in/);
    await open('#auth/signup', /Create account/);

    // ---- a new member
    const ok = await signUp('Smoke Tester', 'smoke' + Date.now() + '@example.com', 'Jb-' + Math.random().toString(36).slice(2) + '-Kq7');
    if (!ok) throw new Error('sign-up failed');
    await open('#playground', /Questions \(/);
    button(/^\s*Save\s*$/, '.pg-top').click();
    await until(() => button(/Save recipe/), 'save dialog', 15000);
    const title = $$('.sv-dialog input[type=text], .sv-dialog input:not([type])')[0];
    type(title, 'Smoke recipe ' + Date.now());
    button(/Save recipe/).click();
    await until(() => /your recipe/.test(($('.pg-top') || {}).innerText || ''), 'saved recipe badge', 20000);
    await open('#recipes/mine', /My recipes/);
    const card = await until(() => $('.rc-card'), 'a recipe card', 15000);
    card.click();
    await until(() => /^#recipes\/./.test(location.hash) && location.hash !== '#recipes/mine' && window.UI_READY, 'recipe page', 20000);
    const recipeHash = location.hash;
    await open(recipeHash, /Questions \(/);
    await open('#playground/recipe/' + recipeHash.split('/')[1], /your recipe/);
    await open('#learn', /Continue reading|Start with chapter 1/);
    await open('#profile', /Your name/);
    await open('#landing', /Ask for a decision/);
    await signOut();

    // ---- admin (ADMIN_EMAILS in Accounts.py): sign up the first time, sign in after that
    const adminPw = 'Jb-smoke-adm-93Kx-7q';
    if (!(await signUp('Admin Tester', 'arkulinskis@gmail.com', adminPw))) await signIn('arkulinskis@gmail.com', adminPw);
    for (const t of ['overview', 'feedback', 'users', 'jev', 'recipes', 'demo']) await open('#admin/' + t, /Admin/);
    await signOut();
    log.push(bad.length ? 'PROBLEMS: ' + bad.join(' | ') : 'PASSED');
    return { ok: !bad.length, log: log };
  } catch (e) {
    log.push(String(e && e.message || e));
    if (bad.length) log.push('PROBLEMS: ' + bad.join(' | '));
    return { ok: false, log: log };
  }
})();
