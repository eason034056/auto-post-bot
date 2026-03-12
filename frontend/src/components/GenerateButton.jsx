/**
 * GenerateButton：開始生成主按鈕
 * 主色按鈕，hover scale、loading pulse 動效
 */
export default function GenerateButton({ onClick, disabled, loading }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className={`w-full rounded-2xl bg-brand py-4 text-lg font-semibold text-white shadow-paper transition-all duration-200 hover:scale-[1.02] hover:shadow-paper-hover active:scale-[0.98] disabled:scale-100 disabled:opacity-50 ${
        loading ? 'animate-pulse-soft' : ''
      }`}
    >
      {loading ? '生成中...' : '開始生成'}
    </button>
  )
}
