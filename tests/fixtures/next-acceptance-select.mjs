/*
 * Copyright 2026 QRun.IO, Inc.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at https://www.apache.org/licenses/LICENSE-2.0
 */

import { execFileSync } from 'node:child_process'
import { appendFileSync, readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

export const AREAS = ['esb', 'help', 'navigation', 'performance', 'processes', 'query', 'records', 'security', 'widgets']
export const SMOKE = [
  'navigation/landing.spec.ts',
  'navigation/navigation.spec.ts',
  'records/crud.spec.ts',
  'query/query-grid.spec.ts',
  'widgets/sample-dashboard.spec.ts',
].map((file) => `tests/acceptance/specs/${file}`)

const sourceAreas = [
  [/help|commandmenu/, 'help'],
  [/widget|dashboard|report|chart|pivot/, 'widgets'],
  [/query|grid|table|filter|search/, 'query'],
  [/record|form|field|input|validation|attachment|preview/, 'records'],
  [/process|bulk/, 'processes'],
  [/navigation|\bnav\b|sidebar|theme|branding|layout/, 'navigation'],
  [/security|auth|login|session|permission/, 'security'],
  [/esb/, 'esb'],
  [/performance/, 'performance'],
]

/** Unknown production/configuration paths expand coverage instead of silently losing it. */
export function selectSpecs(paths) {
  const selected = new Set()
  for (const raw of paths) {
    const file = raw.replaceAll('\\', '/')
    if (file.startsWith('docs/') || /\.md$/i.test(file)) continue
    const specArea = file.match(/^tests\/acceptance\/specs\/([^/]+)\//)?.[1]
    if (specArea && AREAS.includes(specArea)) {
      selected.add(specArea)
      continue
    }
    if (/^(package\.json|pnpm-lock\.yaml|next\.config\.[^/]+)$/.test(file)
      || /^tests\/acceptance\/(playwright\.config\.|support\/|fixture\/|matrix\/|quarantine\.json)/.test(file)
      || /^scripts\/acceptance/.test(file)
      || file === '.github/workflows/acceptance.yml'
      || /^src\/lib\/(api\/|core\/|client|query-client|context\/)/.test(file)) return allSpecs()
    if (file.startsWith('src/')) {
      const matches = sourceAreas.filter(([pattern]) => pattern.test(file.toLowerCase()))
      if (!matches.length) return allSpecs()
      for (const [, area] of matches) selected.add(area)
      continue
    }
    // Unit/mocked tests don't change the real backend; smoke still runs.
    if (/^(tests\/|\.storybook\/)/.test(file)) continue
    return allSpecs()
  }
  return [...AREAS.filter((area) => selected.has(area)).map((area) => `tests/acceptance/specs/${area}`),
    ...SMOKE.filter((file) => !selected.has(file.split('/')[3]))]
}

/** Directory filters include new specs automatically. */
function allSpecs() {
  return AREAS.map((area) => `tests/acceptance/specs/${area}`)
}

/**
 * Build a bounded matrix; each cell owns one browser engine and one backend.
 * @param {{ eventName: string, labels?: string[], paths?: string[] }} input
 */
export function planAcceptance({ eventName, labels = [], paths = [] }) {
  const full = eventName !== 'pull_request' || labels.includes('full-acceptance')
  const counts = full ? { chromium: 3, firefox: 3, webkit: 4, mobile: 4, tablet: 4 } : { chromium: 2, mobile: 2 }
  const include = Object.entries(counts).flatMap(([project, total]) => Array.from({ length: total }, (_, index) => ({
    project, browser: project === 'mobile' ? 'chromium' : project === 'tablet' ? 'webkit' : project,
    shard: index + 1, total,
  })))
  return { mode: full ? 'full' : 'pr', matrix: { include }, specs: full ? [] : selectSpecs(paths) }
}

// Diff both sides of renames, from the PR merge-base (not the current main tip).
// Event data is passed as argv, never interpolated into a shell command.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const event = JSON.parse(readFileSync(process.env.GITHUB_EVENT_PATH, 'utf8'))
  const eventName = process.env.GITHUB_EVENT_NAME
  const labels = (event.pull_request?.labels ?? []).map((label) => label.name)
  const paths = eventName === 'pull_request' && !labels.includes('full-acceptance')
    ? execFileSync('git', ['diff', '--name-only', '--no-renames', '-z', `${event.pull_request.base.sha}...${event.pull_request.head.sha}`, '--'], { encoding: 'utf8' }).split('\0').filter(Boolean)
    : []
  const plan = planAcceptance({ eventName, labels, paths })
  for (const [key, value] of Object.entries(plan)) {
    appendFileSync(process.env.GITHUB_OUTPUT, `${key}=${typeof value === 'string' ? value : JSON.stringify(value)}\n`)
  }
  console.log(JSON.stringify(plan, null, 2))
}
