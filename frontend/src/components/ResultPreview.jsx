import { useState, useEffect } from 'react'
import CopyButton from './CopyButton'
import ImageGallery from './ImageGallery'
import { getImages } from '../api'

/**
 * ResultPreview：結果預覽區
 * - 貼文開頭（hook）可複製
 * - 置頂留言可複製
 * - 圖片網格預覽與下載
 */
export default function ResultPreview({ result, onReset }) {
  const [images, setImages] = useState([])

  useEffect(() => {
    if (result?.output_dir) {
      getImages(result.output_dir)
        .then(setImages)
        .catch(() => setImages([]))
    }
  }, [result?.output_dir])

  return (
    <div className="space-y-8">
      {/* 貼文開頭 */}
      {result?.hook && (
        <div className="rounded-2xl bg-white p-6 shadow-apple">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-apple-gray-500">📝 貼文開頭（鉤子）</h3>
            <CopyButton text={result.hook} />
          </div>
          <p className="whitespace-pre-wrap text-apple-gray-800">{result.hook}</p>
        </div>
      )}

      {/* 置頂留言 */}
      {result?.pinned_comment_text && (
        <div className="rounded-2xl bg-white p-6 shadow-apple">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-apple-gray-500">📌 置頂留言內容</h3>
            <CopyButton text={result.pinned_comment_text} />
          </div>
          <p className="whitespace-pre-wrap text-apple-gray-800">{result.pinned_comment_text}</p>
        </div>
      )}

      {/* 圖片 */}
      {result?.output_dir && (
        <div className="rounded-2xl bg-white p-6 shadow-apple">
          <ImageGallery subdir={result.output_dir} images={images} />
        </div>
      )}

      {/* 重新生成 */}
      <button
        type="button"
        onClick={onReset}
        className="w-full rounded-2xl border-2 border-apple-gray-200 py-3.5 text-base font-medium text-apple-gray-700 transition hover:border-apple-gray-300 hover:bg-apple-gray-50"
      >
        重新生成
      </button>
    </div>
  )
}
