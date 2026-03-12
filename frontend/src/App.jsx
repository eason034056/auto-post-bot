import { useState } from 'react'
import TopicInput from './components/TopicInput'
import GenerateButton from './components/GenerateButton'
import ProgressIndicator from './components/ProgressIndicator'
import ResultPreview from './components/ResultPreview'
import { generateTopic, generate } from './api'

/**
 * App：主應用
 * 整合題目輸入、生成、預覽流程，Editorial + 有機質感 UI
 */
export default function App() {
  const [topic, setTopic] = useState('')
  const [style, setStyle] = useState('')
  const [mock, setMock] = useState(false)
  const [isGeneratingTopic, setIsGeneratingTopic] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleGenerateTopic = async () => {
    setError(null)
    setTopic('') // 點擊 AI 產生題目時先清空原本的主題
    setIsGeneratingTopic(true)
    try {
      const t = await generateTopic()
      setTopic(t)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsGeneratingTopic(false)
    }
  }

  const handleGenerate = async () => {
    const t = topic.trim()
    if (!t) {
      setError('請輸入題目')
      return
    }
    setError(null)
    setResult(null)
    setIsGenerating(true)
    try {
      const res = await generate({
        topic: t,
        style: style || null,
        mock,
      })
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleReset = () => {
    setResult(null)
    setError(null)
  }

  return (
    <div className="min-h-screen bg-paper-50 py-16">
      <div className="mx-auto max-w-2xl px-4 sm:px-6 lg:pl-12 lg:pr-8">
        {/* 標題 - 略向左偏，打破對稱 */}
        <header className="mb-10 text-left opacity-0 animate-fade-in-up animate-delay-100 sm:mb-12">
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink-800 sm:text-4xl">
            青椒家教 · Threads 貼文生成
          </h1>
          <p className="mt-3 text-ink-500">
            為國中家長打造吸引人的圖文貼文
          </p>
        </header>

        {/* 主卡片 - 紙張感，與 header 有輕微 overlap */}
        <main className="-mt-2 rounded-3xl border border-paper-200/80 bg-white/95 p-8 shadow-paper-lg backdrop-blur-sm opacity-0 animate-fade-in-up animate-delay-200 transition-shadow duration-300 hover:shadow-paper-hover">
          {result ? (
            <ResultPreview result={result} onReset={handleReset} />
          ) : (
            <>
              <div className="opacity-0 animate-fade-in-up animate-delay-300">
                <TopicInput
                  topic={topic}
                  onTopicChange={setTopic}
                  onGenerateTopic={handleGenerateTopic}
                  style={style}
                  onStyleChange={setStyle}
                  mock={mock}
                  onMockChange={setMock}
                  isGeneratingTopic={isGeneratingTopic}
                  disabled={isGenerating}
                />
              </div>

              {/* 錯誤訊息 */}
              {error && (
                <div className="mt-4 rounded-xl bg-red-50/80 p-4 text-sm text-red-700 opacity-0 animate-fade-in">
                  {error}
                </div>
              )}

              <div className="mt-8 opacity-0 animate-fade-in-up animate-delay-400">
                <GenerateButton
                  onClick={handleGenerate}
                  disabled={!topic.trim()}
                  loading={isGenerating}
                />
              </div>

              {isGenerating && (
                <div className="mt-8 opacity-0 animate-fade-in-up animate-delay-100">
                  <ProgressIndicator />
                </div>
              )}
            </>
          )}
        </main>

        <footer className="mt-10 text-center text-sm text-ink-400 opacity-0 animate-fade-in-up animate-delay-500">
          Threads 貼文自動生成 AI Agent
        </footer>
      </div>
    </div>
  )
}
