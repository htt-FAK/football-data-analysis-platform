import { Link } from "react-router-dom";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";

export function ServerError() {
  const handleRetry = () => {
    window.location.reload();
  };

  return (
    <div
      className="flex min-h-screen items-center justify-center bg-[#0d0f12] px-4"
      role="main"
      aria-label="500 服务器错误"
    >
      <div className="mx-auto max-w-lg text-center">
        {/* Warning icon */}
        <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-red-500/10">
          <AlertTriangle className="h-12 w-12 text-red-400" aria-hidden="true" />
        </div>

        <h1 className="mb-2 text-7xl font-extrabold tracking-tight text-foreground">
          500
        </h1>
        <h2 className="mb-3 text-2xl font-semibold text-red-400">
          服务器错误
        </h2>
        <p className="mb-10 text-base text-muted-foreground">
          服务器遇到了意外错误，暂时无法处理您的请求。请稍后再试。
        </p>

        <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={handleRetry}
            className="inline-flex h-11 items-center gap-2 rounded-md bg-primary px-6 text-sm font-semibold text-primary-foreground shadow-[0_1px_2px_rgba(0,0,0,0.3)] transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:scale-[0.97]"
            aria-label="稍后重试"
          >
            <RefreshCw className="h-4 w-4" />
            稍后重试
          </button>
          <Link
            to="/"
            className="inline-flex h-11 items-center gap-2 rounded-md border border-border bg-transparent px-6 text-sm font-semibold text-foreground transition-colors hover:bg-secondary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:scale-[0.97]"
            aria-label="返回主页"
          >
            <Home className="h-4 w-4" />
            返回主页
          </Link>
        </div>
      </div>
    </div>
  );
}
