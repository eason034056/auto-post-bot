/**
 * API 封裝：與後端 FastAPI 通訊
 */

const API_BASE = import.meta.env.VITE_API_BASE || '';

export async function generateTopic() {
  const res = await fetch(`${API_BASE}/api/generate-topic`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || '產生題目失敗');
  }
  const data = await res.json();
  return data.topic;
}

export async function getStyles() {
  const res = await fetch(`${API_BASE}/api/styles`);
  if (!res.ok) throw new Error('取得風格列表失敗');
  const data = await res.json();
  return data.styles;
}

export async function generate({ topic, style = null, mock = false, research = true }) {
  const res = await fetch(`${API_BASE}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic: topic.trim(), style, mock, research }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || '生成失敗');
  }
  return res.json();
}

export async function getImages(subdir) {
  const res = await fetch(`${API_BASE}/api/output/${subdir}/images`);
  if (!res.ok) throw new Error('取得圖片列表失敗');
  const data = await res.json();
  return data.images;
}

/**
 * 取得單張圖片的完整 URL（用於預覽與下載）
 */
export function getImageUrl(subdir, filename) {
  return `${API_BASE}/api/output/${subdir}/${filename}`;
}

/**
 * 取得 ZIP 下載 URL（一次下載全部圖片）
 */
export function getDownloadZipUrl(subdir) {
  return `${API_BASE}/api/output/${subdir}/download-zip`;
}

/**
 * 手動觸發：把此次生成記錄到 Google Sheets
 * 回傳 { success, message, already_logged }
 */
export async function logToSheets(subdir) {
  const res = await fetch(`${API_BASE}/api/log-to-sheets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subdir }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || '記錄失敗');
  }
  return res.json();
}
