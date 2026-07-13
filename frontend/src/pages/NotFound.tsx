import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Home } from "lucide-react";

export function NotFound() {
  const navigate = useNavigate();

  return (
    <div
      className="flex min-h-screen items-center justify-center bg-[#0d0f12] px-4"
      role="main"
      aria-label="404 页面不存在"
    >
      <div className="mx-auto max-w-lg text-center">
        {/* Football decorative element */}
        <div className="mb-6 select-none text-[7rem] leading-none" aria-hidden="true">
          ⚽
        </div>

        <h1 className="mb-2 text-7xl font-extrabold tracking-tight text-foreground">
          404
        </h1>
        <h2 className="mb-3 text-2xl font-semibold text-foreground">
          页面不存在
        </h2>
        <p className="mb-10 text-base text-muted-foreground">
          您访问的页面不存在或已被移除，请检查地址是否正确。
        </p>

        <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex h-11 items-center gap-2 rounded-md border border-border bg-transparent px-6 text-sm font-semibold text-foreground transition-colors hover:bg-secondary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:scale-[0.97]"
            aria-label="返回上一页"
          >
            <ArrowLeft className="h-4 w-4" />
            返回上一页
          </button>
          <Link
            to="/"
            className="inline-flex h-11 items-center gap-2 rounded-md bg-primary px-6 text-sm font-semibold text-primary-foreground shadow-[0_1px_2px_rgba(0,0,0,0.3)] transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:scale-[0.97]"
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
