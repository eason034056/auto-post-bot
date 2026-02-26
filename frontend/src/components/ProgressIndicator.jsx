/**
 * ProgressIndicator：生成進度指示
 * Apple 風格載入動畫與步驟提示
 */
export default function ProgressIndicator() {
  return (
    <div className="flex flex-col items-center justify-center gap-8 py-16">
      {/* Spinner */}
      <div className="relative h-16 w-16">
        <div className="absolute inset-0 rounded-full border-4 border-apple-gray-200" />
        <div
          className="absolute inset-0 animate-spin rounded-full border-4 border-transparent border-t-apple-blue"
          style={{ animationDuration: '0.8s' }}
        />
      </div>

      {/* 步驟提示 */}
      <div className="space-y-2 text-center">
        <p className="text-lg font-medium text-apple-gray-800">正在生成貼文...</p>
        <p className="text-sm text-apple-gray-500">
          產生內容 → 產生圖片 → 產生短網址
        </p>
      </div>
    </div>
  )
}
