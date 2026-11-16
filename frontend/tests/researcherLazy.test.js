import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const appPath = resolve(root, 'src/App.vue')
const app = readFileSync(appPath, 'utf8')
const researchers = ['ExperimentPanel', 'ArchiveReview', 'TrialReview', 'DeliveryReview',
  'ReviewObservations', 'TaskResponseReview']

function staticImports(source) {
  return [...source.matchAll(/\bimport\s+(?:[^'"]+?\s+from\s+)?['"](\.[^'"]+)['"]/g)].map(match => match[1])
}

function isFile(path) {
  try { return statSync(path).isFile() } catch { return false }
}

function resolveImport(from, specifier) {
  const base = resolve(dirname(from), specifier)
  return [base, `${base}.vue`, `${base}.js`, resolve(base, 'index.js'), resolve(base, 'index.vue')]
    .find(isFile)
}

function staticGraph(entry) {
  const seen = new Set(), stack = [entry]
  while (stack.length) {
    const file = stack.pop()
    if (seen.has(file) || !/\.(vue|js)$/.test(file)) continue
    seen.add(file)
    for (const specifier of staticImports(readFileSync(file, 'utf8'))) {
      const target = resolveImport(file, specifier)
      if (target && target.startsWith(resolve(root, 'src'))) stack.push(target)
    }
  }
  return [...seen]
}

test('researcher components are not statically reachable from App.vue', () => {
  const reachable = staticGraph(appPath).map(file => file.replaceAll('\\', '/'))
  for (const name of [...researchers, 'IntentEpisodeReview']) {
    assert.ok(!reachable.some(file => file.endsWith(`/components/${name}.vue`)),
      `${name} must not be in the participant static graph`)
  }
  for (const name of researchers) {
    assert.doesNotMatch(app, new RegExp(`import\\s+${name}\\s+from\\s+['"]\\./components/${name}\\.vue['"]`))
    assert.match(app, new RegExp(
      `defineAsyncComponent\\(\\(\\) => import\\('\\./components/${name}\\.vue'\\)\\)`))
  }
})
