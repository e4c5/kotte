/**
 * Smoke tests for SettingsModal — confirms the gear-button entry point reaches
 * a working dialog: theme select round-trips through the persisted store,
 * Save invokes onClose, the close button works, and isOpen=false hides it.
 *
 * Deeper coverage (every numeric input, reset confirmation, etc.) is left to
 * follow-up work; this PR's scope (ROADMAP A1) is wiring + theme switch.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import SettingsModal from '../SettingsModal'
import { useSettingsStore } from '../../stores/settingsStore'

describe('SettingsModal — ROADMAP A1 wiring', () => {
  beforeEach(() => {
    useSettingsStore.setState({
      theme: 'light',
      defaultViewMode: 'auto',
      queryHistoryLimit: 50,
      autoExecuteQuery: false,
      maxNodesForGraph: 5000,
      maxEdgesForGraph: 10000,
      tablePageSize: 50,
      defaultLayout: 'force',
      exportImageFormat: 'png',
      exportImageWidth: 1920,
      exportImageHeight: 1080,
    })
  })

  afterEach(() => {
    useSettingsStore.setState({ theme: 'light' })
  })

  it('does not render when isOpen=false', () => {
    render(<SettingsModal isOpen={false} onClose={vi.fn()} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders the dialog with a theme select reflecting the current store value', () => {
    useSettingsStore.setState({ theme: 'dark' })
    render(<SettingsModal isOpen onClose={vi.fn()} />)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    // The first <select> in the modal is the theme picker; assert it's set to 'dark'.
    expect(screen.getByDisplayValue('Dark')).toBeInTheDocument()
  })

  it('persists a theme change immediately to the store', async () => {
    const user = userEvent.setup()
    render(<SettingsModal isOpen onClose={vi.fn()} />)

    const themeSelect = screen.getByDisplayValue('Light') as HTMLSelectElement
    await user.selectOptions(themeSelect, 'dark')

    expect(useSettingsStore.getState().theme).toBe('dark')
  })

  it('invokes onClose when the close-dialog button is pressed', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<SettingsModal isOpen onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: /close settings dialog/i }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('invokes onClose when Save is pressed', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<SettingsModal isOpen onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: /^save$/i }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
