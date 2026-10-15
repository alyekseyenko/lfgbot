import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("dashboard render error", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="layout">
          <h1>Erro no painel</h1>
          <p className="error">{this.state.error.message}</p>
          <p className="hint">
            Abre a consola do browser (F12) para mais detalhes e recarrega com Ctrl+F5.
          </p>
          <button type="button" onClick={() => window.location.reload()}>
            Recarregar página
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
