import { useState, useEffect } from 'react'
import { getStyles } from '../api'

/**
 * TopicInput：題目輸入區
 * - 手動輸入題目
 * - AI 產生題目按鈕
 * - 開場風格下拉選單
 * - Mock 模式開關
 */
export default function TopicInput({
  topic,
  onTopicChange,
  onGenerateTopic,
  style,
  onStyleChange,
  mock,
  onMockChange,
  isGeneratingTopic,
  disabled,
}) {
  const [styles, setStyles] = useState([])

  useEffect(() => {
    getStyles()
      .then(setStyles)
      .catch(() => setStyles([]))
  }, [])

  return (
    <div className="space-y-5">
      {/* 題目輸入 */}
      <div>
        <label className="mb-2 block text-sm font-medium text-apple-gray-600">貼文題目</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={topic}
            onChange={(e) => onTopicChange(e.target.value)}
            placeholder="例如：假讀書、孩子拖延怎麼辦"
            disabled={disabled}
            className="flex-1 rounded-2xl border border-apple-gray-200 bg-white px-4 py-3.5 text-base text-apple-gray-800 placeholder-apple-gray-400 shadow-sm transition focus:border-apple-blue focus:outline-none focus:ring-2 focus:ring-apple-blue/20 disabled:opacity-60"
          />
          <button
            type="button"
            onClick={onGenerateTopic}
            disabled={disabled || isGeneratingTopic}
            className="rounded-2xl bg-apple-gray-200 px-5 py-3.5 text-sm font-medium text-apple-gray-700 transition hover:bg-apple-gray-300 disabled:opacity-50"
          >
            {isGeneratingTopic ? '產生中...' : 'AI 產生題目'}
          </button>
        </div>
      </div>

      {/* 開場風格 */}
      <div>
        <label className="mb-2 block text-sm font-medium text-apple-gray-600">開場風格（可選）</label>
        <select
          value={style}
          onChange={(e) => onStyleChange(e.target.value)}
          disabled={disabled}
          className="w-full rounded-2xl border border-apple-gray-200 bg-white px-4 py-3.5 text-base text-apple-gray-800 shadow-sm transition focus:border-apple-blue focus:outline-none focus:ring-2 focus:ring-apple-blue/20 disabled:opacity-60"
        >
          <option value="">隨機</option>
          {styles.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Mock 模式 */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={mock}
          onClick={() => onMockChange(!mock)}
          disabled={disabled}
          className={`relative h-8 w-14 rounded-full transition ${
            mock ? 'bg-apple-blue' : 'bg-apple-gray-200'
          }`}
        >
          <span
            className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow transition ${
              mock ? 'left-7' : 'left-1'
            }`}
          />
        </button>
        <span className="text-sm text-apple-gray-600">Mock 模式（測試用，不需 API key）</span>
      </div>
    </div>
  )
}
