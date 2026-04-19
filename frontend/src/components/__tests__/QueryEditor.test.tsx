import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QueryEditor, { getQueryParams } from '../QueryEditor'

describe('getQueryParams', () => {
  it('returns ok=true with the parsed value for an empty object', () => {
    const result = getQueryParams('{}')
    expect(result).toEqual({ ok: true, value: {} })
  })

  it('returns ok=true with the parsed value for a populated object', () => {
    const result = getQueryParams('{"name":"Alice","age":42}')
    expect(result).toEqual({ ok: true, value: { name: 'Alice', age: 42 } })
  })

  it('returns ok=false with a SyntaxError-style message for malformed JSON', () => {
    const result = getQueryParams('{bad')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      // Don't pin to the exact engine message, but it should be non-empty
      // and should not be the empty-string fallback.
      expect(result.error).toMatch(/./)
    }
  })

  it('returns ok=false for a trailing-comma JSON5-style input', () => {
    const result = getQueryParams('{"a":1,}')
    expect(result.ok).toBe(false)
  })

  it('returns ok=false for an empty string (not valid JSON)', () => {
    // Per ROADMAP A10 we deliberately do not special-case empty input;
    // the editor's controlled default is '{}', so reaching this code with ''
    // means the user actively cleared the textarea and should see an error.
    const result = getQueryParams('')
    expect(result.ok).toBe(false)
  })

  it('does NOT silently coerce malformed input to {} (regression on the old behaviour)', () => {
    const result = getQueryParams('not json at all')
    expect(result).not.toEqual({ ok: true, value: {} })
    expect(result.ok).toBe(false)
  })
})

describe('QueryEditor — params validity wiring', () => {
  const renderEditor = (params = '{}', extra: Partial<React.ComponentProps<typeof QueryEditor>> = {}) => {
    const onChange = vi.fn()
    const onParamsChange = vi.fn()
    const onExecute = vi.fn()
    const utils = render(
      <QueryEditor
        value="MATCH (n) RETURN n"
        onChange={onChange}
        params={params}
        onParamsChange={onParamsChange}
        onExecute={onExecute}
        {...extra}
      />
    )
    return { onChange, onParamsChange, onExecute, ...utils }
  }

  // Most of the editor UI only renders when `expanded` is true (focus on the
  // Cypher textarea). Tests that need the params panel or the action row
  // therefore start by focusing the editor.
  const focusAndExpand = async () => {
    const user = userEvent.setup()
    const editor = screen.getByLabelText('Cypher query editor')
    await user.click(editor)
    return user
  }

  it('keeps Execute enabled and shows no error caption when params are valid', async () => {
    renderEditor('{"a":1}')
    await focusAndExpand()
    const execute = screen.getByRole('button', { name: 'Execute query' })
    expect(execute).toBeEnabled()
    expect(execute).toHaveAttribute('aria-disabled', 'false')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('disables Execute and exposes a screen-reader hint when params JSON is invalid', async () => {
    renderEditor('{bad')
    await focusAndExpand()
    const execute = screen.getByRole('button', {
      name: 'Execute query (disabled: parameters JSON is invalid)',
    })
    expect(execute).toBeDisabled()
    expect(execute).toHaveAttribute('aria-disabled', 'true')
    expect(execute).toHaveAttribute(
      'title',
      'Fix the invalid JSON in Parameters to enable Execute'
    )
  })

  it('renders the inline red error caption only when the params panel is open', async () => {
    renderEditor('{bad')
    const user = await focusAndExpand()

    // Panel starts collapsed → caption is not in the DOM, but the dot is.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByTestId('params-invalid-dot')).toBeInTheDocument()

    // Open the panel → caption appears, dot goes away (would duplicate the signal).
    const toggle = screen.getByRole('button', { name: 'Show parameters (parameters JSON is invalid)' })
    await user.click(toggle)

    const caption = screen.getByRole('alert')
    expect(caption).toBeInTheDocument()
    expect(caption.textContent).toMatch(/^Invalid JSON: /)
    expect(screen.queryByTestId('params-invalid-dot')).not.toBeInTheDocument()

    // Textarea is wired to the caption for assistive tech.
    const textarea = screen.getByLabelText('Query parameters')
    expect(textarea).toHaveAttribute('aria-invalid', 'true')
    expect(textarea).toHaveAttribute('aria-describedby', 'query-params-error')
  })

  it('does NOT render the invalid-dot indicator when params are valid', async () => {
    renderEditor('{"ok":true}')
    await focusAndExpand()
    expect(screen.queryByTestId('params-invalid-dot')).not.toBeInTheDocument()
  })

  it('blocks Shift+Enter from firing onExecute when params JSON is invalid', async () => {
    const { onExecute } = renderEditor('{bad')
    await focusAndExpand()
    const editor = screen.getByLabelText('Cypher query editor') as HTMLTextAreaElement
    editor.focus()
    fireEvent.keyDown(globalThis as unknown as Window, { key: 'Enter', shiftKey: true })
    expect(onExecute).not.toHaveBeenCalled()
  })

  it('still fires onExecute on Shift+Enter when params JSON is valid', async () => {
    const { onExecute } = renderEditor('{"a":1}')
    await focusAndExpand()
    const editor = screen.getByLabelText('Cypher query editor') as HTMLTextAreaElement
    editor.focus()
    fireEvent.keyDown(globalThis as unknown as Window, { key: 'Enter', shiftKey: true })
    expect(onExecute).toHaveBeenCalledTimes(1)
  })
})
