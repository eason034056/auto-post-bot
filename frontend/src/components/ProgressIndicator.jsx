/**
 * ProgressIndicator：生成進度指示
 * 精緻 loading 動畫與 staggered 步驟提示
 */
export default function ProgressIndicator() {
  return (
    <div className="flex flex-col items-center justify-center gap-10 py-16">
      {/* Spinner - 雙環設計 */}
      <div className="relative h-16 w-16">
        <div className="absolute inset-0 rounded-full border-2 border-paper-200" />
        <div
          className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-brand border-r-brand/40"
          style={{ animationDuration: '0.9s' }}
        />
      </div>

      {/* 步驟提示 - staggered */}
      <div className="space-y-3 text-center">
        <p className="text-lg font-medium text-ink-800 opacity-0 animate-fade-in-up animate-delay-100">
          正在生成貼文...
        </p>
        <p className="text-sm text-ink-500 opacity-0 animate-fade-in-up animate-delay-200">
          產生內容 → 產生圖片 → 產生短網址
        </p>
      </div>
    </div>
  )
}
