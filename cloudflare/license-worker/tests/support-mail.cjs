/*
 * Offline reproduction of the support-mail review findings, 20 October 2026.
 * Run: node cloudflare/license-worker/tests/support-mail.cjs
 *
 * Loads the actual parsing/sync functions from worker.js and supplies an
 * in-memory IMAP socket and database. No network, real mailbox or DB is used.
 * Assertions cover the corrected behavior, using only local mocks.
 */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const workerPath = path.resolve(__dirname, '../worker.js');
const source = fs.readFileSync(workerPath, 'utf8');
const start = source.indexOf('function imapHeaderMap(');
const end = source.indexOf('function constantTimeEqual(', start);
assert.ok(start >= 0 && end > start, 'Cannot locate the support mail functions');
const segment = source.slice(start, end);

function makeHarness(transcript) {
  const commands = [];
  const writes = [];
  const state = { uid_validity: '9', last_uid: 100 };
  const ticket = {
    id: '00000000-0000-0000-0000-000000000001',
    reference: 'CH-2026-ABCDEF1234',
    contact_email: 'customer@example.test',
  };
  const env = {
    STRATO_SUPPORT_SMTP_USER: 'support@cohentra.digital',
    STRATO_SUPPORT_SMTP_PASSWORD: 'offline-placeholder',
    DB: {
      prepare(sql) {
        return {
          args: [],
          bind(...args) { this.args = args; return this; },
          async first() {
            if (sql.includes('FROM support_mail_sync_state')) return { ...state };
            if (sql.includes('FROM support_tickets')) {
              return this.args[0] === ticket.reference ? ticket : null;
            }
            throw new Error(`Unexpected query: ${sql}`);
          },
          async all() { return {results: writes.filter(w => w.sql.startsWith("INSERT OR IGNORE INTO support_mail_sync_issues")).map(w => ({id:w.args[0],subject:w.args[4]}))}; },
          async run() {
            writes.push({ sql, args: this.args });
            if (sql.startsWith('UPDATE support_mail_sync_state')) {
              state.last_uid = this.args[0];
            }
            return { meta: { changes: 1 } };
          },
        };
      },
    },
  };
  const bytes = typeof transcript === "string" ? new TextEncoder().encode(transcript) : transcript;
  function connect() {
    let offset = 0;
    return {
      readable: {
        getReader() {
          return {
            async read() {
              if (offset >= bytes.length) return { done: true };
              const value = bytes.slice(offset, offset + 65536); offset += value.length;
              return { done: false, value };
            },
            releaseLock() {},
          };
        },
      },
      writable: {
        getWriter() {
          return {
            async write(value) {
              commands.push(new TextDecoder().decode(value).trim());
            },
            releaseLock() {},
          };
        },
      },
      close() {},
    };
  }
  const api = new Function(
    'connect',
    `${segment}; return {syncSupportMailbox,decodeMimeHeader,imapHeaderMap,extractMailText};`,
  )(connect);
  return { api, env, commands, writes, state };
}

function prefix(uids) {
  return [
    '* OK offline IMAP',
    'C1 OK login',
    '* OK [UIDVALIDITY 9] stable',
    'C2 OK selected',
    `* SEARCH ${uids}`,
    'C3 OK search',
    '',
  ].join('\r\n');
}

function messageTranscript(raw) {
  return prefix('101')
    + `* 1 FETCH (UID 101 BODY[] {${Buffer.byteLength(raw, 'utf8')}}\r\n`
    + raw
    + ')\r\nC4 OK fetched\r\n* BYE logout\r\nC5 OK logout\r\n';
}

function rawMessage(subject) {
  return [
    `Subject: ${subject}`,
    'From: Customer <customer@example.test>',
    'In-Reply-To: <00000000-0000-0000-0000-000000000002@cohentra.digital>',
    'References: <00000000-0000-0000-0000-000000000002@cohentra.digital>',
    'Date: Tue, 20 Oct 2026 09:00:00 +0200',
    'Content-Type: text/plain; charset=utf-8',
    '',
    'Dit is mijn nieuwe antwoord.',
    '',
  ].join('\r\n');
}

async function main() {
  const results = [];

  const largeRaw = rawMessage('Re: [CH-2026-ABCDEF1234]') + 'x'.repeat(1_100_000);
  const large = makeHarness(messageTranscript(largeRaw));
  assert.equal((await large.api.syncSupportMailbox(large.env)).linked, 1);
  assert.equal(large.state.last_uid, 101);
  const hugeRaw = rawMessage('Huge screenshot') + 'x'.repeat(8 * 1024 * 1024);
  const laterRaw = rawMessage('Re: [CH-2026-ABCDEF1234]');
  const oversized = makeHarness(prefix('101 102')
    + '* 1 FETCH (UID 101 BODY[] {' + Buffer.byteLength(hugeRaw) + '}\r\n' + hugeRaw + ')\r\nC4 OK fetched\r\n'
    + '* 2 FETCH (UID 102 BODY[] {' + Buffer.byteLength(laterRaw) + '}\r\n' + laterRaw + ')\r\nC5 OK fetched\r\n'
    + '* BYE logout\r\nC6 OK logout\r\n');
  const oversizeResult = await oversized.api.syncSupportMailbox(oversized.env);
  assert.equal(oversizeResult.linked, 1);
  assert.equal(oversizeResult.issues.length, 1);
  assert.equal(oversized.state.last_uid, 102);
  assert.equal(oversizeResult.issues[0].subject, 'Huge screenshot');

  // Positive control: otherwise-identical unencoded reference links correctly.
  const control = makeHarness(messageTranscript(rawMessage('Re: [CH-2026-ABCDEF1234]')));
  const controlResult = await control.api.syncSupportMailbox(control.env);
  assert.equal(controlResult.linked, 1);
  assert.equal(control.state.last_uid, 101);
  results.push({
    control: 'plain subject links the customer message',
    result: controlResult,
  });

  const unicode = makeHarness(messageTranscript(rawMessage('Re: [CH-2026-ABCDEF1234] café')
    .replace('From: Customer', 'From: José')
    .replace('Dit is mijn nieuwe antwoord.', 'Mijn café werkt weer ✅')));
  assert.equal((await unicode.api.syncSupportMailbox(unicode.env)).linked, 1);
  const received = unicode.writes.find(w => w.sql.startsWith('INSERT OR IGNORE INTO support_ticket_messages'));
  assert.equal(received.args[2], 'José');
  assert.equal(received.args[4], 'Mijn café werkt weer ✅');
  const disconnected = makeHarness(prefix('101') + '* 1 FETCH (UID 101 BODY[] {9000000}\\r\\n');
  await assert.rejects(() => disconnected.api.syncSupportMailbox(disconnected.env), /verbinding.*gesloten/);
  assert.equal(disconnected.state.last_uid, 100);

  const subject = '=?UTF-8?Q?Re=3A_=5BCH-2026-?=\r\n =?UTF-8?Q?ABCDEF1234=5D?=';
  const folded = makeHarness(messageTranscript(rawMessage(subject)));
  const decodedSubject = folded.api.decodeMimeHeader(
    folded.api.imapHeaderMap(`Subject: ${subject}`).get('subject'),
  );
  const foldedResult = await folded.api.syncSupportMailbox(folded.env);
  assert.equal(decodedSubject, 'Re: [CH-2026-ABCDEF1234]');
  assert.deepEqual(foldedResult, { checked: 1, linked: 1, skipped: 0, more: false, issues: [] });
  assert.equal(folded.state.last_uid, 101);
  assert.equal(
    folded.writes.filter(write => write.sql.startsWith('INSERT OR IGNORE INTO support_ticket_messages')).length,
    1,
  );
  results.push({
    finding: 'P2: adjacent MIME encoded words break reference matching',
    expectedSubject: 'Re: [CH-2026-ABCDEF1234]',
    decodedSubject,
    result: foldedResult,
    cursorAfterSkippedReply: folded.state.last_uid,
  });

  const isoRaw = Buffer.concat([
    Buffer.from('Content-Type: text/plain; charset=iso-8859-1\r\nContent-Transfer-Encoding: 8bit\r\n\r\n'),
    Buffer.from([0x63, 0x61, 0x66, 0xe9]),
  ]);
  // Raw bytes remain intact until the MIME charset is inspected.
  const actual = folded.api.extractMailText(isoRaw.toString('latin1'));
  assert.equal(actual, 'caf\u00e9');
  results.push({
    finding: 'P2: non-UTF8 8bit body is corrupted before MIME decoding',
    expected: 'caf\u00e9',
    actual,
  });

  console.log('PASS: >1 MB mail imported; >8 MB mail drained and persistently reported; next reply imported; MIME subject linked; ISO-8859-1 preserved.');
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
