import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const source = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)),
  '../src/components/RevisionSupport.vue'), 'utf8')

test('B0 compact revision card does not claim a system interpretation', () => {
  assert.match(source, /structured \? 'Review this system interpretation\. You can correct the source, target charts, or conditions\.' : 'You can change the source, target charts, or conditions in a revised proposal\.'/)
  assert.match(source, /structured \? 'Correct interpretation' : 'Modify revision'/)
  assert.match(source, /structured \? 'Revision support' : 'Revision'/)
  assert.equal((source.match(/Review this system interpretation/g) || []).length, 1)
  assert.equal((source.match(/Correct interpretation/g) || []).length, 1)
  assert.match(source, /@click="emit\('revise'\)"/)
})
