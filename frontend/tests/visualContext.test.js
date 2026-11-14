import test from 'node:test'
import assert from 'node:assert/strict'
import { visualContextLabel } from '../src/visualContext.js'

const reference = { revision: 6, view_ids: ['v2', 'v3'], entities: { v2: ['bed_bath_table'] } }

test('visual status distinguishes local capture, queued image and actual delivery', () => {
  assert.equal(visualContextLabel(reference, null, 0), 'No chart image yet')
  assert.equal(visualContextLabel(reference, null, 3), 'Preparing canvas v6')
  assert.equal(visualContextLabel(reference, { reference, status: 'captured' }, 3), 'Captured locally · v6')
  assert.equal(visualContextLabel(reference, { reference, status: 'queued' }, 3), 'Waiting for audio · v6')
  assert.equal(visualContextLabel(reference, { reference, status: 'sent' }, 3), 'Frame sent to model · v6')
})

test('a late receipt cannot label a different chart selection or category highlight as sent', () => {
  const receipt = { reference, status: 'sent' }
  assert.equal(visualContextLabel({ ...reference, revision: 7 }, receipt, 3), 'Preparing canvas v7')
  assert.equal(visualContextLabel({ ...reference, view_ids: ['v1'] }, receipt, 3), 'Preparing canvas v6')
  assert.equal(visualContextLabel({ ...reference, entities: { v2: ['sports_leisure'] } }, receipt, 3), 'Preparing canvas v6')
})
