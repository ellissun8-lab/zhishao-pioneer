// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { PredictionPanel } from './PredictionPanel'

vi.mock('../api/client', () => ({
  api: { predict: vi.fn() },
}))

afterEach(() => cleanup())

describe('PredictionPanel reset', () => {
  it('clears stale rule predictions when the demo is reset', async () => {
    vi.mocked(api.predict).mockResolvedValue({
      horizon_minutes: 10,
      risk_score: 42,
      risk_trend: 'up',
      gather_probability: 0.4,
      zone_entry_probability: 0.3,
      predicted_agents: 3,
      model: 'transparent_rule_probability_v1',
      synthetic: true,
    })
    const view = render(<PredictionPanel currentRisk={30} resetVersion={0} />)

    fireEvent.click(screen.getByRole('button', { name: /\+10 min/ }))
    expect(await screen.findByText('42')).toBeTruthy()

    view.rerender(<PredictionPanel currentRisk={30} resetVersion={1} />)
    expect(screen.queryByText('42')).toBeNull()
  })

  it('ignores a stale rule prediction that resolves after reset', async () => {
    let resolvePrediction!: (value: Awaited<ReturnType<typeof api.predict>>) => void
    vi.mocked(api.predict).mockReturnValue(new Promise((resolve) => { resolvePrediction = resolve }))
    const view = render(<PredictionPanel currentRisk={30} resetVersion={0} />)
    fireEvent.click(screen.getByRole('button', { name: /\+10 min/ }))

    view.rerender(<PredictionPanel currentRisk={30} resetVersion={1} />)
    await act(async () => {
      resolvePrediction({
        horizon_minutes: 10,
        risk_score: 42,
        risk_trend: 'up',
        gather_probability: 0.4,
        zone_entry_probability: 0.3,
        predicted_agents: 3,
        model: 'transparent_rule_probability_v1',
        synthetic: true,
      })
    })

    expect(screen.queryByText('42')).toBeNull()
  })
})
