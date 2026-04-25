import { useEffect, useState } from 'react'

/**
 * ProgressIndicator：動態生成進度
 *
 * Props（皆為 optional，沒給時退化為純 spinner）：
 * - phase:        目前階段代碼（research / content / images / short_url ...）
 * - step:         主階段序號（1-based）
 * - total:        主階段總數（research 開啟時 4，否則 3）
 * - subCurrent:   子進度當前數（圖片階段：第幾張）
 * - subTotal:     子進度總數（圖片階段：共幾張）
 * - message:      文字訊息
 * - startedAt:    開始時間（Date.now() 秒級）— 用來顯示已耗時
 *
 * 💡 為什麼分主進度與子進度：研究階段一個 phase 就要 3-5 分鐘，
 *    若只有 step/total 進度條會卡很久不動。圖片階段反而快但張數多，
 *    給 sub-progress 才有「在動」的感覺。兩條進度條互補。
 */
export default function ProgressIndicator({
  phase = '',
  step = 0,
  total = 0,
  subCurrent = 0,
  subTotal = 0,
  message = '',
  startedAt = null,
}) {
  // 已耗時計時器（每秒更新）
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!startedAt) return undefined
    const tick = () => setElapsed(Math.floor((Date.now() - startedAt) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [startedAt])

  // 主階段進度百分比（基於 step/total）
  // 💡 完成的階段算 100%，當前階段先算 50%（避免進度條突然跳很大）
  const mainPct = total > 0 ? Math.min(100, Math.round(((step - 0.5) / total) * 100)) : 0
  // 子進度（僅圖片階段有意義）
  const subPct = subTotal > 0 ? Math.round((subCurrent / subTotal) * 100) : 0

  // 階段標籤對應
  const phaseLabel = (() => {
    if (phase === 'research') return '深度研究'
    if (phase === 'research_done') return '研究完成'
    if (phase === 'content') return '產生內容'
    if (phase === 'content_done') return '內容完成'
    if (phase === 'images') return '產生圖片'
    if (phase === 'short_url') return '短網址'
    if (phase === 'mock') return 'Mock 模式'
    return '生成中'
  })()

  const elapsedDisplay = (() => {
    const m = Math.floor(elapsed / 60)
    const s = elapsed % 60
    return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`
  })()

  return (
    <div className="flex flex-col items-center justify-center gap-8 py-10">
      {/* Spinner - 雙環設計 */}
      <div className="relative h-14 w-14">
        <div className="absolute inset-0 rounded-full border-2 border-paper-200" />
        <div
          className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-brand border-r-brand/40"
          style={{ animationDuration: '0.9s' }}
        />
      </div>

      {/* 階段標題 + 已耗時 */}
      <div className="w-full max-w-md space-y-1.5 text-center">
        <div className="flex items-baseline justify-center gap-3">
          <p className="text-base font-medium text-ink-800">
            {phaseLabel}
            {total > 0 && (
              <span className="ml-2 text-sm text-ink-500">
                （{step}/{total}）
              </span>
            )}
          </p>
          {startedAt && (
            <span className="text-xs text-ink-400">已耗時 {elapsedDisplay}</span>
          )}
        </div>
        {message && (
          <p className="text-sm leading-relaxed text-ink-500">{message}</p>
        )}
      </div>

      {/* 主階段進度條 */}
      {total > 0 && (
        <div className="w-full max-w-md">
          <div className="mb-1 flex items-center justify-between text-xs text-ink-400">
            <span>主流程</span>
            <span>{mainPct}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-paper-200">
            <div
              className="h-full rounded-full bg-brand transition-all duration-500"
              style={{ width: `${mainPct}%` }}
            />
          </div>
        </div>
      )}

      {/* 子進度條（圖片階段才顯示）*/}
      {subTotal > 0 && phase === 'images' && (
        <div className="w-full max-w-md">
          <div className="mb-1 flex items-center justify-between text-xs text-ink-400">
            <span>圖片</span>
            <span>{subCurrent}/{subTotal}（{subPct}%）</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-paper-200">
            <div
              className="h-full rounded-full bg-brand/60 transition-all duration-300"
              style={{ width: `${subPct}%` }}
            />
          </div>
        </div>
      )}

      {/* 研究階段提示（時間最久，給使用者預期）*/}
      {phase === 'research' && (
        <p className="max-w-md text-center text-xs leading-relaxed text-ink-400">
          深度研究會做多輪搜尋與推理，預期 3-5 分鐘。<br />
          完成後會自動進入下一階段，無需操作。
        </p>
      )}
    </div>
  )
}
