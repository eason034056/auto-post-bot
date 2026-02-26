import { useState } from 'react'

/**
 * CopyButton：一鍵複製文字到剪貼簿
 * 複製成功後短暫顯示「已複製」提示
 */
export default function CopyButton({ text, label = '複製', className = '' }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (err) {
      console.error('Copy failed:', err)
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all duration-200 ${
        copied
          ? 'bg-green-500/20 text-green-700'
          : 'bg-apple-gray-100 text-apple-gray-700 hover:bg-apple-gray-200'
      } ${className}`}
    >
      {copied ? (
        <>
          <span className="text-green-600">✓</span>
          已複製
        </>
      ) : (
        <>
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          {label}
        </>
      )}
    </button>
  )
}
