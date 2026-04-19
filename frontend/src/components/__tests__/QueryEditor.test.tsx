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

  it('returns ok=true and preserves nested arrays/objects as values', () => {
    const result = getQueryParams('{"ids":[1,2,3],"meta":{"k":"v"}}')
    expect(result).toEqual({
      ok: true,
      value: { ids: [1, 2, 3], meta: { k: 'v' } },
    })
  })

  it('returns ok=false with a SyntaxError-style message for malformed JSON', () => {
    const result = getQueryParams('{bad')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      // Always prefixed with the user-facing "Invalid JSON: " marker so the
      // editor can render the message verbatim in the inline alert caption.
      expect(result.error).toMatch(/^Invalid JSON: /)
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

  // Backend contract is `params: Optional[Dict[str, Any]]` (Pydantic),
  // so the top-level value MUST be a JSON object. Anything else parses
  // fine on the client but 422s at the API; surface the failure here.
  // Kept as a table so new shape-reject cases can be added with one line
  // (also dodges Sonar's duplication detector, which flagged ~30 lines of
  // near-identical `it` blocks here as a single-file duplicated block).
  it.each([
    { label: 'an empty JSON array', input: '[]' },
    { label: 'a populated JSON array', input: '[1,2,3]' },
    { label: 'the JSON literal null', input: 'null' },
    { label: 'a bare number', input: '42' },
    { label: 'a JSON string literal', input: '"hello"' },
    { label: 'the JSON literal true', input: 'true' },
  ])('returns ok=false with the shape-error message for $label', ({ input }) => {
    const result = getQueryParams(input)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toBe('Parameters must be a JSON object')
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

  it('disables Execute and surfaces a shape-error caption when params is a JSON array (not an object)', async () => {
    renderEditor('[]')
    const user = await focusAndExpand()

    // Execute reflects the same "invalid" state as a syntax error.
    const execute = screen.getByRole('button', {
      name: 'Execute query (disabled: parameters JSON is invalid)',
    })
    expect(execute).toBeDisabled()
    expect(execute).toHaveAttribute('aria-disabled', 'true')

    // Open the params panel and confirm the shape-specific message
    // (no "Invalid JSON: " prefix; this case parses fine, the shape is wrong).
    const toggle = screen.getByRole('button', { name: 'Show parameters (parameters JSON is invalid)' })
    await user.click(toggle)

    const caption = screen.getByRole('alert')
    expect(caption).toBeInTheDocument()
    expect(caption.textContent).toBe('Parameters must be a JSON object')
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
