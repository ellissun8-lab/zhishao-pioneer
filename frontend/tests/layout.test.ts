import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')

describe('desktop CV layout contract', () => {
  it('lets the desktop workspace grow vertically instead of squeezing panels into 100vh', () => {
    expect(css).toContain('grid-template-rows: auto 188px')
    expect(css).toContain('.right-column { grid-template-rows: auto auto auto; align-content: start; }')
  })

  it('keeps a usable minimum height for the CV panel', () => {
    expect(css).toContain('.cv-panel { display: grid; grid-template-rows: 39px auto; min-height: 360px; }')
  })
})
