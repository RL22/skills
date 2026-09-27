// Page templates: lo-fi page archetypes for `{ "type": "page", "template": "<name>" }`.
// Contract: CSI.pages[name] = (node, box) => ({ title, children })
//   box = { w, h } is the inner content area (after padding and the page label). children are ordinary
//   components (see references/spec-schema.md) and must fit box.h at every size from 120×156 to 320×416:
//   derive heights from box (Math.round(box.h * k)), keep text short, prefer squiggles/X-boxes, one hatched
//   primary action at most. node may carry template options (e.g. node.count) — document them in references/pages.md.
(function () {
  const P = {};
  const H = (box, k) => Math.max(8, Math.round(box.h * k));
  const clamp = (value, fallback, min, max) => Math.min(max, Math.max(min, Number.isFinite(Number(value)) ? Math.round(Number(value)) : fallback));
  const times = (n, fn) => Array.from({ length: n }, (_, i) => fn(i));
  const smallImage = (b, k = 0.12, label) => ({ type: 'image', h: H(b, k), ...(label ? { label } : {}) });
  const copy = (w = '65%', thick = false) => ({ type: 'squiggle', w, thick });
  const tile = (b, k = 0.11) => ({ type: 'card', pad: 4, gap: 4, children: [smallImage(b, k), copy()] });
  const person = (b) => ({ type: 'card', pad: 4, gap: 3, children: [{ type: 'avatar', d: H(b, 0.13) }, copy('70%')] });
  const itemRow = (b, k = 0.1) => ({ type: 'row', gap: 5, valign: 'center', children: [smallImage(b, k), copy('52%'), { type: 'icons', n: 1, d: 9 }] });

  P.basic = (n, b) => ({ title: 'Basic', children: [{ type: 'image', h: H(b, 0.9) }] });

  P.cart = (n, b) => ({
    title: 'Cart',
    children: [
      { type: 'stack', gap: 3, children: times(clamp(n.count, 3, 1, 4), () => itemRow(b, 0.09)) },
      { type: 'divider' },
      { type: 'button', size: 'sm', w: '50%', align: 'right' },
    ],
  });

  P.landing = (n, b) => ({ title: 'Landing', children: [
    { type: 'nav', n: 2, menu: b.w < 180 },
    copy('70%', true),
    smallImage(b, 0.3),
    { type: 'button', label: 'Start', size: 'sm', w: '48%' },
  ] });

  P.grid = (n, b) => {
    const cols = clamp(n.cols, 3, 2, 4);
    return { title: 'Grid', children: [copy('45%', true), { type: 'grid', cols, gap: 5, children: times(cols * 2, () => tile(b, 0.07)) }] };
  };

  P.columns = (n, b) => {
    const cols = clamp(n.cols, 3, 2, 4);
    return { title: 'Columns', children: [copy('55%', true), { type: 'grid', cols, gap: 5, children: times(cols, () => ({ type: 'card', pad: 4, gap: 4, children: [copy('80%', true), { type: 'squiggle', lines: 3 }] })) }] };
  };

  P.rows = (n, b) => ({ title: 'Rows', children: [copy('45%', true), ...times(clamp(n.count, 3, 2, 4), () => itemRow(b, 0.1))] });

  P.list = (n, b) => ({ title: 'List', children: [copy('45%', true), { type: 'list', n: clamp(n.count, 3, 1, 4), mark: 'dash' }] });

  P.article = (n, b) => ({ title: 'Article', children: [copy('78%', true), copy('42%'), smallImage(b, 0.27), { type: 'paragraph', lines: 3 }] });

  P.blog = (n, b) => ({ title: 'Blog', children: [copy('45%', true), { type: 'grid', cols: 2, gap: 5, children: times(4, () => tile(b, 0.08)) }] });

  P.calendar = (n, b) => ({ title: 'Calendar', children: [
    { type: 'row', gap: 5, justify: 'between', children: [copy('42%', true), { type: 'icons', n: 2, d: 10 }] },
    { type: 'table', rows: 4, cols: 7, h: H(b, 0.62), header: true },
  ] });

  P.event = (n, b) => ({ title: 'Event', children: [smallImage(b, 0.27), copy('70%', true), { type: 'badge', label: 'Date' }, { type: 'button', label: 'Join', size: 'sm', w: '45%' }] });

  P.team = (n, b) => {
    const count = clamp(n.count, 4, 1, 6);
    return { title: 'Team', children: [copy('42%', true), { type: 'grid', cols: count < 3 ? count : 3, gap: 5, children: times(count, () => person(b)) }] };
  };

  P.bio = (n, b) => ({ title: 'Bio', children: [
    { type: 'row', gap: 6, valign: 'center', children: [{ type: 'avatar', d: H(b, 0.25), figure: true }, { type: 'stack', gap: 4, children: [copy('80%', true), copy('55%')] }] },
    { type: 'paragraph', lines: 3 },
    { type: 'icons', n: 3, d: 11 },
  ] });

  P.features = (n, b) => ({ title: 'Features', children: [copy('50%', true), { type: 'grid', cols: 3, gap: 5, children: times(b.w < 150 ? 3 : 6, () => ({ type: 'card', pad: 4, gap: 3, children: [{ type: 'plus' }, copy('70%')] })) }] });

  P.gallery = (n, b) => {
    const count = clamp(n.count, 6, 1, 8);
    return { title: 'Gallery', children: [copy('42%', true), { type: 'grid', cols: count < 3 ? count : 3, gap: 5, children: times(count, () => smallImage(b, 0.14)) }] };
  };

  P.slideshow = (n, b) => ({ title: 'Slideshow', children: [smallImage(b, 0.6), { type: 'row', gap: 5, justify: 'between', children: [{ type: 'button', label: '‹', variant: 'outline', size: 'sm', w: '20%' }, { type: 'icons', n: 3, d: 6 }, { type: 'button', label: '›', variant: 'outline', size: 'sm', w: '20%' }] }] });

  P.video = (n, b) => ({ title: 'Video', children: [{ type: 'video', h: H(b, 0.55) }, copy('60%', true), copy('85%')] });

  P.news = (n, b) => ({ title: 'News', children: [copy('58%', true), { type: 'row', gap: 5, valign: 'top', children: [smallImage(b, 0.27), { type: 'stack', gap: 4, children: [copy('90%', true), { type: 'paragraph', lines: 2 }] }] }, { type: 'list', n: 2, mark: 'dash' }] });

  P.magazine = (n, b) => ({ title: 'Magazine', children: [copy('68%', true), { type: 'grid', cols: 2, gap: 5, children: [smallImage(b, 0.38), { type: 'stack', gap: 4, children: [copy('90%', true), { type: 'paragraph', lines: 4 }] }] }, { type: 'divider' }, { type: 'row', gap: 5, children: [copy('42%'), copy('42%')] }] });

  P.board = (n, b) => ({ title: 'Board', children: [
    { type: 'tabs', items: ['~', '~~'], active: 0 },
    { type: 'grid', cols: 3, gap: 5, children: times(3, () => ({ type: 'card', pad: 4, gap: 3, children: [copy('70%', true), { type: 'list', n: 1, mark: 'dash' }, { type: 'add', h: H(b, 0.1) }] })) },
  ] });

  P.contact = (n, b) => ({ title: 'Contact', children: [copy('50%', true), { type: 'input', placeholder: '~~' }, { type: 'textarea', rows: 1, placeholder: '~~~' }, { type: 'button', label: 'Send', size: 'sm', w: '45%' }] });

  P.form = (n, b) => ({ title: 'Form', children: [copy('40%', true), { type: 'input', placeholder: '~' }, { type: 'dropdown', value: '~' }, { type: 'button', size: 'sm', w: '45%' }] });

  P.login = (n, b) => ({ title: 'Login', children: [copy('45%', true), { type: 'input', placeholder: '~' }, { type: 'input', placeholder: '~' }, { type: 'button', label: 'Log in', size: 'sm', w: '55%' }] });

  P.signup = (n, b) => ({ title: 'Sign up', children: [copy('50%', true), { type: 'input', placeholder: '~' }, { type: 'input', placeholder: '~' }, { type: 'button', label: 'Sign up', size: 'sm', w: '58%' }] });

  P.chat = (n, b) => ({ title: 'Chat', children: [
    { type: 'row', gap: 5, children: [{ type: 'avatar', d: 22 }, copy('45%', true)] },
    { type: 'card', pad: 5, children: [copy('78%')] },
    { type: 'card', pad: 5, align: 'right', w: '72%', children: [copy('78%')] },
    { type: 'row', gap: 5, children: [{ type: 'input', placeholder: '~' }, { type: 'button', label: '›', size: 'sm', w: 30 }] },
  ] });

  P.comments = (n, b) => ({ title: 'Comments', children: [copy('45%', true), ...times(2, () => ({ type: 'row', gap: 5, valign: 'top', children: [{ type: 'avatar', d: 20 }, { type: 'stack', gap: 3, children: [copy('45%', true), copy('90%')] }] })), { type: 'input', placeholder: '~' }] });

  P.documents = (n, b) => ({ title: 'Documents', children: [
    { type: 'row', gap: 5, justify: 'between', children: [copy('48%', true), { type: 'plus' }] },
    { type: 'table', cells: [['~', '~'], ['~~', '~'], ['~~~', '~']], h: H(b, 0.55) },
  ] });

  P.profile = (n, b) => ({ title: 'Profile', children: [
    { type: 'row', gap: 6, valign: 'center', children: [{ type: 'avatar', d: H(b, 0.24), figure: true }, { type: 'stack', gap: 3, children: [copy('75%', true), copy('55%'), { type: 'button', label: 'Follow', size: 'sm', w: '70%' }] }] },
    { type: 'tabs', items: ['~', '~~'], active: 0 },
    { type: 'grid', cols: 3, gap: 4, children: times(3, () => smallImage(b, 0.13)) },
  ] });

  P.products = (n, b) => {
    const count = clamp(n.count, 6, 1, 8);
    return { title: 'Products', children: [{ type: 'grid', cols: count < 3 ? count : 3, gap: 5, children: times(count, () => tile(b, 0.07)) }] };
  };

  P.product = (n, b) => ({ title: 'Product', children: [smallImage(b, 0.38), copy('65%', true), copy('45%'), { type: 'row', gap: 5, children: [{ type: 'dropdown', value: '~' }, { type: 'button', label: 'Buy', size: 'sm', w: '45%' }] }] });

  P.checkout = (n, b) => ({ title: 'Checkout', children: [{ type: 'input', placeholder: '~' }, { type: 'row', gap: 5, children: [{ type: 'input', placeholder: '~' }, { type: 'input', placeholder: '~' }] }, { type: 'divider' }, { type: 'button', label: 'Pay', size: 'sm', w: '50%', align: 'right' }] });

  P.pricing = (n, b) => ({ title: 'Pricing', children: [copy('48%', true), { type: 'grid', cols: 3, gap: 5, children: times(3, (_, i) => ({ type: 'card', pad: 4, gap: 3, selected: i === 1, children: [copy('70%', true), copy('45%', true), { type: 'list', n: 1, mark: 'check' }, { type: 'button', label: i === 1 ? 'Choose' : '~', variant: i === 1 ? 'primary' : 'outline', size: 'sm' }] })) }] });

  P.tabs = (n, b) => ({ title: 'Tabs', children: [{ type: 'tabs', items: ['One', 'Two', '~'], active: 0 }, smallImage(b, 0.32), { type: 'paragraph', lines: 3 }] });

  P.map = (n, b) => ({ title: 'Map', children: [{ type: 'input', placeholder: '~' }, { type: 'placeholder', label: 'Map', h: H(b, 0.5) }, { type: 'icons', n: 3, d: 10, align: 'center' }] });

  P.directory = (n, b) => ({ title: 'Directory', children: [{ type: 'input', placeholder: '~' }, { type: 'grid', cols: 2, gap: 5, children: times(4, () => ({ type: 'row', gap: 4, valign: 'center', children: [{ type: 'avatar', d: 20 }, { type: 'stack', gap: 2, children: [copy('75%', true), copy('50%')] }] })) }] });

  P.search = (n, b) => ({ title: 'Search', children: [{ type: 'input', placeholder: 'Search' }, { type: 'badge', label: '12 results' }, { type: 'list', n: 2, mark: 'dash' }] });

  P.sitemap = (n, b) => ({ title: 'Sitemap', children: [copy('45%', true), { type: 'table', cells: [['Home', '~', '~'], ['', '~', '~'], ['', '~', '~']], h: H(b, 0.62), header: false }] });

  P.dashboard = (n, b) => ({ title: 'Dashboard', children: [
    { type: 'row', gap: 5, justify: 'between', children: [copy('48%', true), { type: 'avatar', d: 20 }] },
    { type: 'grid', cols: 3, gap: 5, children: times(3, () => ({ type: 'card', pad: 4, gap: 3, children: [copy('55%'), copy('70%', true)] })) },
    { type: 'chart', h: H(b, 0.35), highlight: 3 },
  ] });

  P.settings = (n, b) => ({ title: 'Settings', children: [{ type: 'tabs', items: ['Account', '~'], active: 0 }, { type: 'row', gap: 5, justify: 'between', children: [copy('42%'), { type: 'toggle', on: true }] }, { type: 'button', label: 'Save', size: 'sm', w: '42%' }] });

  P.thanks = (n, b) => ({ title: 'Thanks', children: [{ type: 'plus', align: 'center' }, { type: 'heading', text: 'Thank you', size: 17, align: 'center' }, { type: 'paragraph', lines: 2, align: 'center' }, { type: 'button', label: 'Continue', size: 'sm', w: '58%', align: 'center' }] });

  P.error404 = (n, b) => ({ title: '404', children: [{ type: 'heading', text: '404', size: 28, align: 'center' }, smallImage(b, 0.24), { type: 'button', label: 'Go home', variant: 'outline', size: 'sm', w: '58%', align: 'center' }] });

  P.external = (n, b) => ({ title: 'External', children: [{ type: 'placeholder', label: 'External', h: H(b, 0.48), dashed: true }, copy('70%', true), { type: 'button', label: 'Visit', variant: 'outline', size: 'sm', w: '48%', align: 'center' }] });

  CSI.pages = P;
})();
