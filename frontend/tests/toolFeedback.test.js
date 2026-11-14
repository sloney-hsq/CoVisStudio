import test from 'node:test'
import assert from 'node:assert/strict'
import { toolFeedback } from '../src/toolFeedback.js'

test('only a real committed receipt is presented as a chart update', () => {
  const result = toolFeedback({ tool: 'apply_revision', status: 'completed', committed: true,
    summary: 'Updated two service charts', revision: 7, view_numbers: [2, 3] })
  assert.deepEqual(result, { tone: 'committed', title: 'Updated two service charts', detail: 'Charts 2, 3 · Committed · v7' })
  assert.equal(toolFeedback({ tool: 'preview_revision', status: 'completed', committed: false }).tone, 'pending')
  assert.equal(toolFeedback({ tool: 'apply_revision', status: 'awaiting_confirmation', committed: false }).tone, 'pending')
  assert.equal(toolFeedback({ tool: 'edit_charts', status: 'failed', message: 'Choose a valid metric.' }).tone, 'failed')
  assert.equal(toolFeedback({ tool: 'read_dashboard', status: 'completed', committed: false }), null)
})
import { recordReceipt, markReceiptDisplayed } from '../src/toolFeedback.js'

test('request receipts preserve the earlier result without assigning it to a new request', () => {
  const receipts = {}
  recordReceipt(receipts, { request_id: 'first-half', status: 'committed', revision: 7, view_numbers: [2, 3] })
  recordReceipt(receipts, { request_id: 'q1', status: 'no_changes', revision: 7, view_numbers: [] })
  assert.equal(receipts['first-half'].status, 'committed')
  assert.equal(toolFeedback(receipts.q1).title, 'No chart changes')
  assert.equal(toolFeedback(receipts.q1).detail, 'This reply did not update the charts.')
  recordReceipt(receipts, { request_id: 'first-half', status: 'committed', revision: 7, view_numbers: [2, 3] })
  assert.equal(receipts.q1.status, 'no_changes')
  assert.match(toolFeedback(receipts['first-half']).detail, /Committed · v7/)
  markReceiptDisplayed(receipts, 6)
  assert.equal(!!receipts['first-half'].displayed, false)
  markReceiptDisplayed(receipts, 7)
  assert.match(toolFeedback(receipts['first-half']).detail, /Displayed · v7/)
  assert.equal(!!receipts.q1.displayed, false)
})

test('a later failure or pending choice keeps the same request’s applied version and rendered fact', () => {
  const receipts = {}
  recordReceipt(receipts, { request_id: 'partial', status: 'completed', committed: true, revision: 7, view_numbers: [2] })
  markReceiptDisplayed(receipts, 7)
  recordReceipt(receipts, { request_id: 'partial', status: 'failed', committed: false, revision: 7, message: 'Unknown metric.' })
  assert.equal(receipts.partial.committed, true)
  assert.match(toolFeedback(receipts.partial).detail, /Charts 2 · Displayed · v7/)
  assert.match(toolFeedback(receipts.partial).detail, /Unknown metric/)
  recordReceipt(receipts, { request_id: 'partial', status: 'awaiting_confirmation', committed: true, revision: 7, view_numbers: [2] })
  assert.match(toolFeedback(receipts.partial).detail, /Displayed · v7/)
  assert.doesNotMatch(toolFeedback(receipts.partial).detail, /current charts are unchanged/i)
})



test('request receipt UI is scoped to conversation messages, never saved recordings', async () => {
  const { readFile } = await import('node:fs/promises')
  const app = await readFile(new URL('../src/App.vue', import.meta.url), 'utf8')
  const recordings = app.slice(app.indexOf('v-for="item in media.filter'))
  assert.equal(recordings.includes('receiptForMessage(message)'), false)
  assert.equal((app.match(/class="turn-receipt"/g) || []).length, 1)
})
