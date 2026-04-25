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

/**
 * 產生 10 個候選題目並標出 AI 推薦項，供使用者挑選
 * @returns { candidates: [{angle, topic}], recommended: string, has_signals: boolean }
 */
export async function generateTopicCandidates() {
  const res = await fetch(`${API_BASE}/api/generate-topic-candidates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || '產生候選題目失敗');
  }
  return res.json();
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

/**
 * 串流生成：用 SSE（Server-Sent Events）逐階段接收進度，最後拿 result
 *
 * @param {object} params { topic, style, mock, research }
 * @param {(event: object) => void} onProgress 收到 progress 事件時的回呼
 * @returns {Promise<object>} resolve 為最終 complete 事件中的 result；任一 error 事件 → reject
 *
 * 💡 為什麼用 fetch 而不用 EventSource：EventSource 不支援 POST、也不支援自訂 headers。
 *    我們需要 POST body 傳 params，所以走 fetch + ReadableStream 手動解析 SSE。
 *
 * SSE 格式：每個事件 `data: <json>\n\n`，所以以 `\n\n` 切分事件邊界即可。
 */
export async function generateStream({ topic, style = null, mock = false, research = true }, onProgress) {
  const res = await fetch(`${API_BASE}/api/generate-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
    body: JSON.stringify({ topic: topic.trim(), style, mock, research }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || '生成失敗');
  }
  if (!res.body) {
    throw new Error('伺服器未回傳串流內容');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult = null;

  // ⚠️ 一旦進入 read loop，必須 drain 到 done，否則 reader 會 lock 住 connection
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // 以 \n\n 切事件邊界；最後一段可能還沒結束，留在 buffer 等下一輪
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';

    for (const ev of events) {
      const dataLine = ev.split('\n').find((l) => l.startsWith('data: '));
      if (!dataLine) continue;
      let payload;
      try {
        payload = JSON.parse(dataLine.slice(6));
      } catch (e) {
        console.warn('SSE 事件解析失敗', ev, e);
        continue;
      }

      if (payload.type === 'error') {
        throw new Error(payload.detail || '生成失敗');
      }
      if (payload.type === 'complete') {
        finalResult = payload.result;
        // complete 之後可能還有 buffer 殘留但實質已結束 — 仍 drain 到 done
        continue;
      }
      // progress 事件
      if (onProgress) onProgress(payload);
    }
  }

  if (!finalResult) {
    throw new Error('伺服器未回傳完成事件');
  }
  return finalResult;
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
