import { useState } from 'react'
import { getImageUrl, getDownloadZipUrl } from '../api'

/**
 * ImageGallery：圖片網格預覽
 * 點擊可放大，支援下載全部（ZIP 或逐張）
 */
export default function ImageGallery({ subdir, images }) {
  const [selected, setSelected] = useState(null)

  const handleDownloadAll = () => {
    // 使用 ZIP 端點一次下載，避免 CORS 與多次請求問題
    const a = document.createElement('a')
    a.href = getDownloadZipUrl(subdir)
    a.download = `${subdir}.zip`
    a.click()
  }

  if (!images?.length) return null

  return (
    <>
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-apple-gray-800">圖片預覽</h3>
        <button
          type="button"
          onClick={handleDownloadAll}
          className="rounded-xl bg-apple-blue px-4 py-2.5 text-sm font-medium text-white transition hover:opacity-90"
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
            className="overflow-hidden rounded-2xl bg-apple-gray-100 shadow-apple transition hover:shadow-apple-lg"
          >
            <img
              src={getImageUrl(subdir, filename)}
              alt={filename}
              className="h-40 w-full object-cover"
            />
            <p className="truncate px-2 py-1.5 text-xs text-apple-gray-500">{filename}</p>
          </button>
        ))}
      </div>

      {/* 放大預覽 Modal */}
      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setSelected(null)}
        >
          <img
            src={getImageUrl(subdir, selected)}
            alt={selected}
            className="max-h-[90vh] max-w-full rounded-2xl object-contain shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  )
}
