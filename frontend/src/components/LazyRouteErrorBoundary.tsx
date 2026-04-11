import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  readonly children: ReactNode
}

interface State {
  hasError: boolean
}

export class LazyRouteErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Lazy route failed to load', error, info.componentStack)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen w-full flex-col items-center justify-center gap-6 bg-zinc-950 px-6 text-center text-zinc-200">
          <p className="text-lg font-medium">Could not load this screen</p>
          <p className="max-w-md text-sm text-zinc-400">
            The page chunk failed to load. Check your connection and try again.
          </p>
          <button
            type="button"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            onClick={() => {
              this.setState({ hasError: false })
              globalThis.location.reload()
            }}
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
