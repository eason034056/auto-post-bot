import { useState, useEffect } from 'react'
import { getStyles, generateTopicCandidates } from '../api'

/**
 * TopicInput：題目輸入區
 * - 手動輸入題目
 * - AI 產生 10 個候選題目，使用者點選一個 → 填入輸入框
 * - 開場風格下拉選單
 * - 深度研究 / Mock 模式開關
 *
 * 💡 把「AI 產生題目」從「直接得到 1 個」改成「先看 10 候選再選」，
 *    讓使用者保有對題目方向的選擇權，AI 只負責發想 + 推薦。
 */
export default function TopicInput({
  topic,
  onTopicChange,
  style,
  onStyleChange,
  mock,
  onMockChange,
  research,
  onResearchChange,
  disabled,
}) {
  const [styles, setStyles] = useState([])
  const [candidates, setCandidates] = useState([])
  const [recommended, setRecommended] = useState('')
  const [hasSignals, setHasSignals] = useState(false)
  const [isLoadingCandidates, setIsLoadingCandidates] = useState(false)
  const [candidatesError, setCandidatesError] = useState(null)

  useEffect(() => {
    getStyles()
      .then(setStyles)
      .catch(() => setStyles([]))
  }, [])

  const handleGenerateCandidates = async () => {
    setCandidatesError(null)
    setIsLoadingCandidates(true)
    setCandidates([])
    setRecommended('')
    try {
      const data = await generateTopicCandidates()
      setCandidates(data.candidates || [])
      setRecommended(data.recommended || '')
      setHasSignals(Boolean(data.has_signals))
    } catch (err) {
      setCandidatesError(err.message)
    } finally {
      setIsLoadingCandidates(false)
    }
  }

  const handleSelectCandidate = (chosenTopic) => {
    onTopicChange(chosenTopic)
    setCandidates([])
    setRecommended('')
    setCandidatesError(null)
  }

  const handleClearCandidates = () => {
    setCandidates([])
    setRecommended('')
    setCandidatesError(null)
  }

  return (
    <div className="space-y-6">
      {/* 題目輸入 */}
      <div>
        <label className="mb-2 block text-sm font-medium text-ink-600">貼文題目</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={topic}
            onChange={(e) => onTopicChange(e.target.value)}
            placeholder="例如：假讀書、孩子拖延怎麼辦"
            disabled={disabled}
            className="flex-1 rounded-2xl border border-paper-200 bg-white px-4 py-3.5 text-base text-ink-800 shadow-sm transition-all duration-200 placeholder-ink-400 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 focus:shadow-paper disabled:opacity-60"
          />
          <button
            type="button"
            onClick={handleGenerateCandidates}
            disabled={disabled || isLoadingCandidates}
            className="rounded-2xl bg-paper-200 px-5 py-3.5 text-sm font-medium text-ink-700 transition-all duration-200 hover:bg-paper-300 hover:shadow-paper disabled:opacity-50"
          >
            {isLoadingCandidates ? '產生候選中...' : 'AI 產生候選'}
          </button>
        </div>

        {/* 候選清單 loading */}
        {isLoadingCandidates && (
          <div className="mt-4 rounded-2xl border border-paper-200 bg-paper-50/60 p-5 text-sm text-ink-500">
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-brand" />
              <span>抓取本週教育圈動態並批量產生 10 個候選題目（約 60-90 秒）...</span>
            </div>
          </div>
        )}

        {/* 候選清單 error */}
        {candidatesError && !isLoadingCandidates && (
          <div className="mt-4 rounded-xl bg-red-50/80 p-4 text-sm text-red-700">
            {candidatesError}
          </div>
        )}

        {/* 候選清單 */}
        {candidates.length > 0 && !isLoadingCandidates && (
          <div className="mt-4 rounded-2xl border border-paper-200 bg-paper-50/60 p-4 sm:p-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-sm font-medium text-ink-700">
                候選題目（{candidates.length} 個，點選使用）
                {hasSignals && (
                  <span className="ml-2 rounded-full bg-emerald-100/70 px-2 py-0.5 text-xs font-normal text-emerald-700">
                    含本週時事
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleGenerateCandidates}
                  disabled={disabled || isLoadingCandidates}
                  className="rounded-lg px-3 py-1.5 text-xs font-medium text-ink-600 transition-colors hover:bg-paper-200 disabled:opacity-50"
                >
                  重新產生
                </button>
                <button
                  type="button"
                  onClick={handleClearCandidates}
                  disabled={disabled}
                  className="rounded-lg px-3 py-1.5 text-xs font-medium text-ink-500 transition-colors hover:bg-paper-200 disabled:opacity-50"
                >
                  關閉
                </button>
              </div>
            </div>

            <ul className="space-y-2">
              {candidates.map((c, i) => {
                const isRecommended = c.topic === recommended
                return (
                  <li key={`${c.topic}-${i}`}>
                    <button
                      type="button"
                      onClick={() => handleSelectCandidate(c.topic)}
                      disabled={disabled}
                      className={`group w-full rounded-xl border bg-white px-4 py-3 text-left transition-all duration-200 hover:shadow-paper disabled:opacity-50 ${
                        isRecommended
                          ? 'border-brand/60 ring-1 ring-brand/20'
                          : 'border-paper-200 hover:border-paper-300'
                      }`}
                    >
                      <div className="mb-1 flex items-center gap-2">
                        {c.angle && (
                          <span className="rounded-md bg-paper-100 px-2 py-0.5 text-xs font-medium text-ink-500">
                            {c.angle}
                          </span>
                        )}
                        {isRecommended && (
                          <span className="rounded-md bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand">
                            ★ AI 推薦
                          </span>
                        )}
                      </div>
                      <div className="text-sm leading-relaxed text-ink-800 group-hover:text-ink-900">
                        {c.topic}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </div>

      {/* 開場風格 */}
      <div>
        <label className="mb-2 block text-sm font-medium text-ink-600">開場風格（可選）</label>
        <select
          value={style}
          onChange={(e) => onStyleChange(e.target.value)}
          disabled={disabled}
          className="w-full rounded-2xl border border-paper-200 bg-white px-4 py-3.5 text-base text-ink-800 shadow-sm transition-all duration-200 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 disabled:opacity-60"
        >
          <option value="">隨機</option>
          {styles.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* 深度研究 */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={research}
          onClick={() => onResearchChange(!research)}
          disabled={disabled}
          className={`relative h-8 w-14 rounded-full transition-all duration-300 ${
            research ? 'bg-brand' : 'bg-paper-200'
          }`}
        >
          <span
            className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow-paper transition-all duration-300 ${
              research ? 'left-7' : 'left-1'
            }`}
          />
        </button>
        <span className="text-sm text-ink-600">深度研究（Perplexity 即時搜尋，提升內容品質）</span>
      </div>

      {/* Mock 模式 */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={mock}
          onClick={() => onMockChange(!mock)}
          disabled={disabled}
          className={`relative h-8 w-14 rounded-full transition-all duration-300 ${
            mock ? 'bg-brand' : 'bg-paper-200'
          }`}
        >
          <span
            className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow-paper transition-all duration-300 ${
              mock ? 'left-7' : 'left-1'
            }`}
          />
        </button>
        <span className="text-sm text-ink-600">Mock 模式（測試用，不需 API key）</span>
      </div>
    </div>
  )
}
