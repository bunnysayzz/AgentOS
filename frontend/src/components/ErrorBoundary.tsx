import { Component, type ReactNode, type ErrorInfo } from 'react'
import { AlertCircleIcon, RefreshCwIcon } from '@/components/Icons'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
            <AlertCircleIcon size={28} className="text-red-400" />
          </div>
          <h2 className="text-xl font-semibold text-surface-100 mb-2">Something went wrong</h2>
          <p className="text-sm text-surface-400 text-center max-w-md mb-6">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button
            onClick={this.handleRetry}
            className="btn-primary flex items-center gap-2"
          >
            <RefreshCwIcon size={16} />
            Try again
          </button>
          <details className="mt-6 w-full max-w-md">
            <summary className="text-xs text-surface-500 cursor-pointer hover:text-surface-400">
              Error details
            </summary>
            <pre className="mt-2 text-xs text-surface-500 bg-surface-900 p-3 rounded-xl overflow-auto max-h-32">
              {this.state.error?.stack}
            </pre>
          </details>
        </div>
      )
    }

    return this.props.children
  }
}


