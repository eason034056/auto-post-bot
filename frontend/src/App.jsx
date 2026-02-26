import { useState } from 'react'
import TopicInput from './components/TopicInput'
import GenerateButton from './components/GenerateButton'
import ProgressIndicator from './components/ProgressIndicator'
import ResultPreview from './components/ResultPreview'
import { generateTopic, generate } from './api'

/**
 * App：主應用
 * 整合題目輸入、生成、預覽流程，Apple 風格 UI
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
    <div className="min-h-screen bg-apple-gray-50 py-12">
      <div className="mx-auto max-w-2xl px-4">
        {/* 標題 */}
        <header className="mb-12 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-apple-gray-800">
            青椒家教 · Threads 貼文生成
          </h1>
          <p className="mt-2 text-apple-gray-500">
            為國中家長打造吸引人的圖文貼文
          </p>
        </header>

        {/* 主卡片 */}
        <main className="rounded-3xl bg-white p-8 shadow-apple-lg">
          {result ? (
            <ResultPreview result={result} onReset={handleReset} />
          ) : (
            <>
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

              {/* 錯誤訊息 */}
              {error && (
                <div className="mt-4 rounded-xl bg-red-50 p-4 text-sm text-red-700">
                  {error}
                </div>
              )}

              <div className="mt-8">
                <GenerateButton
                  onClick={handleGenerate}
                  disabled={!topic.trim()}
                  loading={isGenerating}
                />
              </div>

              {isGenerating && (
                <div className="mt-8">
                  <ProgressIndicator />
                </div>
              )}
            </>
          )}
        </main>

        <footer className="mt-8 text-center text-sm text-apple-gray-400">
          Threads 貼文自動生成 AI Agent
        </footer>
      </div>
    </div>
  )
}
