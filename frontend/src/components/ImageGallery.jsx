import { useCallback, useEffect, useState } from 'react'
import { getImageUrl, getDownloadZipUrl } from '../api'

/**
 * ImageGallery：圖片網格預覽
 * 點擊可放大，支援下載全部（ZIP 或逐張）
 * Modal 內可用左右按鈕或 ← → 鍵切換、Esc 關閉
 */
export default function ImageGallery({ subdir, images }) {
  // 💡 從『選中的檔名』改成『選中的 index』，方便 prev/next 計算
  const [selectedIdx, setSelectedIdx] = useState(null)
  const isOpen = selectedIdx !== null
  const total = images?.length ?? 0
  const hasMultiple = total > 1

  const close = useCallback(() => setSelectedIdx(null), [])

  // 💡 用 modular arithmetic 讓首尾互相 wrap：
  //    第一張按 prev → 跳到最後一張；最後一張按 next → 回到第一張
  const prev = useCallback(() => {
    setSelectedIdx((i) => (i - 1 + total) % total)
  }, [total])
  const next = useCallback(() => {
    setSelectedIdx((i) => (i + 1) % total)
  }, [total])

  // ⚠️ 鍵盤事件綁在 window 上才能不依賴焦點；記得 cleanup
  useEffect(() => {
    if (!isOpen) return
    const handler = (e) => {
      if (e.key === 'Escape') close()
      else if (e.key === 'ArrowLeft') prev()
      else if (e.key === 'ArrowRight') next()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen, close, prev, next])

  const handleDownloadAll = () => {
    const a = document.createElement('a')
    a.href = getDownloadZipUrl(subdir)
    a.download = `${subdir}.zip`
    a.click()
  }

  if (!images?.length) return null

  return (
    <>
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg font-semibold text-ink-800">圖片預覽</h3>
        <button
          type="button"
          onClick={handleDownloadAll}
          className="rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white shadow-paper transition-all duration-200 hover:scale-105 hover:shadow-paper-hover"
        >
          下載全部
        </button>
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
        {images.map((filename, idx) => (
          <button
            key={filename}
            type="button"
            onClick={() => setSelectedIdx(idx)}
            className="overflow-hidden rounded-2xl bg-paper-100 shadow-paper transition-all duration-200 hover:-translate-y-1 hover:shadow-paper-hover"
          >
            <img
              src={getImageUrl(subdir, filename)}
              alt={filename}
              className="h-40 w-full object-cover"
            />
            <p className="truncate px-2 py-1.5 text-xs text-ink-500">{filename}</p>
          </button>
        ))}
      </div>

      {/* 放大預覽 Modal - backdrop blur + 淡入 + 左右切換 */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink-800/60 p-4 backdrop-blur-sm animate-fade-in"
          onClick={close}
        >
          {/* 左按鈕（只有 >1 張才顯示） */}
          {hasMultiple && (
            <button
              type="button"
              // ⚠️ stopPropagation 防止冒泡觸發 backdrop 的 close
              onClick={(e) => {
                e.stopPropagation()
                prev()
              }}
              aria-label="上一張"
              className="absolute left-4 top-1/2 z-10 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-2xl font-bold text-ink-800 shadow-lg transition hover:scale-110 hover:bg-white sm:left-8 sm:h-14 sm:w-14"
            >
              ‹
            </button>
          )}

          <img
            src={getImageUrl(subdir, images[selectedIdx])}
            alt={images[selectedIdx]}
            className="max-h-[90vh] max-w-full rounded-2xl object-contain shadow-2xl animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          />

          {/* 右按鈕 */}
          {hasMultiple && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                next()
              }}
              aria-label="下一張"
              className="absolute right-4 top-1/2 z-10 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-2xl font-bold text-ink-800 shadow-lg transition hover:scale-110 hover:bg-white sm:right-8 sm:h-14 sm:w-14"
            >
              ›
            </button>
          )}

          {/* 進度計數 */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-full bg-white/90 px-4 py-1.5 text-sm font-medium text-ink-800 shadow-lg">
            {selectedIdx + 1} / {total}
          </div>
        </div>
      )}
    </>
  )
}
