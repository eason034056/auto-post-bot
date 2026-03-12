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
  const strategyText = Array.isArray(result?.content_strategy)
    ? result.content_strategy.join(' -> ')
    : ''

  useEffect(() => {
    if (result?.output_dir) {
      getImages(result.output_dir)
        .then(setImages)
        .catch(() => setImages([]))
    }
  }, [result?.output_dir])

  return (
    <div className="space-y-8">
      {/* 結構策略 */}
      {(result?.structure_name || strategyText) && (
        <div className="rounded-2xl border border-paper-200/60 bg-paper-50/50 p-6 shadow-paper opacity-0 animate-fade-in-up animate-delay-100">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h3 className="text-sm font-medium text-ink-500">貼文結構策略</h3>
              {result?.structure_name && (
                <p className="mt-2 font-display text-lg font-semibold text-ink-800">
                  {result.structure_name}
                </p>
              )}
            </div>
            {strategyText && <CopyButton text={strategyText} label="複製策略" />}
          </div>

          {Array.isArray(result?.content_strategy) && result.content_strategy.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {result.content_strategy.map((item) => (
                <span
                  key={item}
                  className="rounded-full bg-brand/10 px-3 py-1.5 text-sm font-medium text-brand-dark transition-transform duration-200 hover:scale-105"
                >
                  {item}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 引導討論 */}
      {result?.discussion_question && (
        <div className="rounded-2xl border border-paper-200/60 bg-paper-50/50 p-6 shadow-paper opacity-0 animate-fade-in-up animate-delay-200">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-ink-500">引導討論句</h3>
            <CopyButton text={result.discussion_question} />
          </div>
          <p className="whitespace-pre-wrap text-ink-800">{result.discussion_question}</p>
        </div>
      )}

      {/* 貼文開頭 */}
      {result?.hook && (
        <div className="rounded-2xl border border-paper-200/60 bg-paper-50/50 p-6 shadow-paper opacity-0 animate-fade-in-up animate-delay-300">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-ink-500">📝 貼文開頭（鉤子）</h3>
            <CopyButton text={result.hook} />
          </div>
          <p className="whitespace-pre-wrap text-ink-800">{result.hook}</p>
        </div>
      )}

      {/* 置頂留言 */}
      {result?.pinned_comment_text && (
        <div className="rounded-2xl border border-paper-200/60 bg-paper-50/50 p-6 shadow-paper opacity-0 animate-fade-in-up animate-delay-400">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-ink-500">📌 置頂留言內容</h3>
            <CopyButton text={result.pinned_comment_text} />
          </div>
          <p className="whitespace-pre-wrap text-ink-800">{result.pinned_comment_text}</p>
        </div>
      )}

      {/* 圖片 */}
      {result?.output_dir && (
        <div className="rounded-2xl border border-paper-200/60 bg-paper-50/50 p-6 shadow-paper opacity-0 animate-fade-in-up animate-delay-500">
          <ImageGallery subdir={result.output_dir} images={images} />
        </div>
      )}

      {/* 重新生成 */}
      <button
        type="button"
        onClick={onReset}
        className="w-full rounded-2xl border-2 border-paper-200 py-3.5 text-base font-medium text-ink-700 transition-all duration-200 hover:border-paper-300 hover:bg-paper-50"
      >
        重新生成
      </button>
    </div>
  )
}
