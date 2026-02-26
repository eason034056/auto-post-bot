/**
 * GenerateButton：開始生成主按鈕
 * Apple 風格大圓角、主色按鈕
 */
export default function GenerateButton({ onClick, disabled, loading }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className="w-full rounded-2xl bg-apple-blue py-4 text-lg font-semibold text-white shadow-apple transition hover:opacity-95 disabled:opacity-50"
    >
      {loading ? '生成中...' : '開始生成'}
    </button>
  )
}
