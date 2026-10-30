// Offline regression tests against the support UI code extracted from worker.js.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const workerPath = path.resolve(__dirname, '../worker.js');
const worker = fs.readFileSync(workerPath, 'utf8');
const start = worker.indexOf("var supportMeId=null,currentSupportTicketId=''");
const end = worker.indexOf('const permissionOptions=', start);
assert(start > -1 && end > start);
const source = worker.slice(start, end);
const tick = () => new Promise(resolve => setImmediate(resolve));

function makeHarness() {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) {
      const classes = new Set();
      elements.set(id, {
        id, value: '', checked: false, disabled: false, dataset: {}, innerHTML: '',
        textContent: '', style: {}, scrollTop: 0, scrollHeight: 0,
        classList: {
          add(...names) { names.forEach(name => classes.add(name)); },
          remove(...names) { names.forEach(name => classes.delete(name)); },
          contains(name) { return classes.has(name); },
          toggle(name, force) {
            const on = force === undefined ? !classes.has(name) : force;
            if (on) classes.add(name); else classes.delete(name);
            return on;
          },
        },
        focus() {},
        setAttribute() {},
        toggleAttribute() {},
        querySelector(selector) { return element(id + selector); },
        requestSubmit() { return this.onsubmit({ preventDefault() {} }); },
      });
    }
    return elements.get(id);
  }
  const rows = ['A', 'B'].map((id, i) => ({
    id, reference: 'SUP-' + id, status: 'new', subject: 'Ticket ' + id,
    contact_email: id.toLowerCase() + '@example.test',
    customer_name: 'Customer ' + id, message: 'Original message ' + id,
    created_at: '2026-10-20T10:00:00.000Z',
    updated_at: '2026-10-20T10:0' + (2 - i) + ':00.000Z',
  }));
  const posts = [];
  const context = {
    console, Date, Boolean, Number, String, Math, JSON, encodeURIComponent,
    token: 'test-session', sessionStorage: { getItem(k) { return this[k] || null }, setItem(k,v) { this[k] = v } },
    cxFilter: 'active', openCustomer(id) { this.openedCustomer = id },
    $: element, document: { addEventListener() {}, querySelectorAll() { return []; } },
    setInterval() {}, can: () => true, safe: value => String(value ?? ''),
    supportTicketRows: rows, updateOverview() {}, renderSupportAvatars() {},
    cxInitials: () => 'AB', setView() {},
    api(url, options) {
      if (options?.method === 'POST' && url.endsWith('/replies')) {
        return new Promise((resolve, reject) => posts.push({
          url, payload: JSON.parse(options.body), resolve, reject,
        }));
      }
      if (url === '/api/support/tickets') return Promise.resolve({ tickets: rows });
      const id = decodeURIComponent(url.split('/').at(-1));
      return Promise.resolve({ ticket: { ...rows.find(row => row.id === id) }, replies: [] });
    },
  };
  vm.createContext(context);
  vm.runInContext(source, context, { filename: workerPath });
  return { context, element, rows, posts };
}

async function main() {
  {
    const h = makeHarness();
    await h.context.openSupportTicket('A');
    h.element('supportReplyMessage').value = 'Unsent answer for A';
    await h.context.openSupportTicket('B');
    await h.context.openSupportTicket('A');
    assert.equal(h.element('supportReplyMessage').value, 'Unsent answer for A');
  }
  {
    const h = makeHarness();
    await h.context.openSupportTicket('A');
    h.element('supportReplyMessage').value = 'Unsent answer for A';
    h.element('supportSearch').value = 'Ticket B';
    h.element('supportSearch').oninput();
    await tick();
    assert.equal(h.context.currentSupportTicketId, 'B');
    assert.equal(h.element('supportReplyMessage').value, '');
    h.element('supportSearch').value = '';
    h.element('supportSearch').oninput();
    await h.context.openSupportTicket('A');
    assert.equal(h.element('supportReplyMessage').value, 'Unsent answer for A');
  }
  {
    const h = makeHarness();
    await h.context.openSupportTicket('A');
    h.element('supportReplyMessage').value = 'One internal note';
    h.element('supportNoteToggle').checked = true;
    const ctrlEnter = { key: 'Enter', ctrlKey: true, preventDefault() {} };
    h.element('supportReplyMessage').onkeydown(ctrlEnter);
    assert.equal(h.element('supportReplyButton').disabled, true);
    h.element('supportReplyMessage').onkeydown(ctrlEnter);
    assert.equal(h.posts.length, 1);
    h.posts.forEach(post => post.resolve({ ok: true }));
    await tick();
  }
  {
    const h = makeHarness();
    await h.context.openSupportTicket('A');
    h.element('supportReplyMessage').value = 'First reply';
    const send = h.context.sendSupportReply({ message: 'First reply' });
    assert.equal(h.element('supportReplyMessage').disabled, false);
    h.element('supportReplyMessage').value = 'Additional second draft typed during sending';
    h.posts[0].resolve({ ok: true });
    await send;
    assert.equal(h.element('supportReplyMessage').value, 'Additional second draft typed during sending');
  }
  {
    const h = makeHarness();
    await h.context.openSupportTicket('A');
    h.element('supportReplyMessage').value = 'Reply for A';
    const send = h.context.sendSupportReply({ message: 'Reply for A' });
    await h.context.openSupportTicket('B');
    h.element('supportReplyMessage').value = 'Draft for B';
    h.posts[0].reject(new Error('Failed to send A'));
    await send;
    assert.equal(h.context.currentSupportTicketId, 'B');
    assert.equal(h.element('supportDetailError').textContent, '');
    await h.context.openSupportTicket('A');
    assert.equal(h.element('supportDetailError').textContent, 'Failed to send A');
    assert.equal(h.element('supportReplyMessage').value, 'Reply for A');
  }
  {
    const h = makeHarness();
    await h.context.openSupportTicket('A');
    h.element('supportReplyMessage').value = 'Survives refresh';
    h.element('supportReplyMessage').oninput();
    const restored = makeHarness();
    restored.context.sessionStorage = h.context.sessionStorage;
    restored.context.restoreSupportDrafts();
    await restored.context.openSupportTicket('A');
    assert.equal(restored.element('supportReplyMessage').value, 'Survives refresh');
    restored.context.token = 'different-login';
    restored.context.restoreSupportDrafts();
    await restored.context.openSupportTicket('A');
    assert.equal(restored.element('supportReplyMessage').value, '');
  }
  {
    const h = makeHarness();
    await h.context.openSupportTicket('A');
    h.context.supportDetail.customer_id = 'customer-A';
    let opened;
    h.context.openCustomer = id => { opened = id };
    h.element('supportDetailFacts').onclick({target:{closest:()=>({})}});
    assert.equal(opened, 'customer-A');
    assert.equal(h.context.cxFilter, 'all');
  }
  {
    const h = makeHarness();
    const pages = [];
    h.context.api = async url => {
      pages.push(url);
      return url.includes('?cursor=') ? {tickets:[h.rows[1]],next_cursor:null} : {tickets:[h.rows[0]],next_cursor:'A'};
    };
    h.context.currentSupportTicketId = 'A';
    await h.context.loadSupportTickets();
    assert.equal(h.context.supportTicketRows.length, 2);
    assert.deepEqual(pages, ['/api/support/tickets','/api/support/tickets?cursor=A']);
  }
  console.log('PASS: drafts survive switching, search and refresh; session isolation; no double submit; newer text and ticket-specific errors preserved; correct customer; all pages loaded.');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
