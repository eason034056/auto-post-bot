import { useState } from 'react'
import { getImageUrl, getDownloadZipUrl } from '../api'

/**
 * ImageGallery：圖片網格預覽
 * 點擊可放大，支援下載全部（ZIP 或逐張）
 * hover lift、modal backdrop blur + 淡入
 */
export default function ImageGallery({ subdir, images }) {
  const [selected, setSelected] = useState(null)

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
        {images.map((filename) => (
          <button
            key={filename}
            type="button"
            onClick={() => setSelected(filename)}
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

      {/* 放大預覽 Modal - backdrop blur + 淡入 */}
      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink-800/60 p-4 backdrop-blur-sm animate-fade-in"
          onClick={() => setSelected(null)}
        >
          <img
            src={getImageUrl(subdir, selected)}
            alt={selected}
            className="max-h-[90vh] max-w-full rounded-2xl object-contain shadow-2xl animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  )
}
