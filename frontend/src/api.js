import axios from "axios";

export const API_BASE_URL = "http://localhost:8003";

const HEALTH_TIMEOUT_MS = 8_000;
const UPLOAD_TIMEOUT_MS = 20_000;
const ASR_TIMEOUT_MS = 25_000;
const EXTRACT_TIMEOUT_MS = 20_000;
const SEARCH_TIMEOUT_MS = 30_000;
const FINALIZE_TIMEOUT_MS = 48_000;
const AUDIO_TIMEOUT_MS = 15_000;

export const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (isCanceledError(error)) {
      return Promise.reject(error);
    }
    const data = error.response?.data;
    if (data instanceof Blob) {
      try {
        const parsed = JSON.parse(await data.text());
        if (parsed?.error) {
          error.apiError = parsed.error;
        }
      } catch {
        // 音频错误体不是 JSON 时，走通用提示。
      }
    } else if (data?.error) {
      error.apiError = data.error;
    }
    return Promise.reject(error);
  },
);

export function isCanceledError(error) {
  return axios.isCancel(error) || error?.code === "ERR_CANCELED" || error?.name === "CanceledError";
}

export function toUserMessage(error, fallback) {
  if (error?.userMessage) {
    return error.userMessage;
  }
  if (error?.apiError?.message) {
    return error.apiError.message;
  }
  if (error?.code === "ECONNABORTED") {
    return "请求超时，请稍后重试";
  }
  if (!error?.response) {
    return "网络连接失败，请检查后端是否已启动";
  }
  return fallback;
}

function unwrapData(response) {
  const payload = response.data;
  if (!payload || typeof payload !== "object" || payload.data == null) {
    const error = new Error("响应格式异常");
    error.userMessage = "服务返回格式异常，请稍后重试";
    throw error;
  }
  return payload.data;
}

export async function checkHealth(signal) {
  const response = await api.get("/health", {
    timeout: HEALTH_TIMEOUT_MS,
    signal,
  });
  return unwrapData(response);
}

export async function uploadRecording(blob, signal) {
  const form = new FormData();
  form.append("file", blob, "recording.webm");
  const response = await api.post("/upload", form, {
    timeout: UPLOAD_TIMEOUT_MS,
    signal,
  });
  return unwrapData(response);
}

export async function recognizeAudio(audioId, signal) {
  const response = await api.post(
    "/asr",
    { audio_id: audioId },
    {
      timeout: ASR_TIMEOUT_MS,
      signal,
    },
  );
  return unwrapData(response);
}

export async function extractMeetup(text, city, signal) {
  const response = await api.post(
    "/extract",
    { text, city },
    {
      timeout: EXTRACT_TIMEOUT_MS,
      signal,
    },
  );
  return unwrapData(response);
}

export async function searchMeetup(extract, signal) {
  const response = await api.post(
    "/search",
    {
      city_a: extract.city_a,
      address_a: extract.address_a,
      city_b: extract.city_b,
      address_b: extract.address_b,
      category: extract.category,
    },
    {
      timeout: SEARCH_TIMEOUT_MS,
      signal,
    },
  );
  return unwrapData(response);
}

export async function finalizeMeetup(searchId, signal) {
  const response = await api.post(
    "/finalize",
    { search_id: searchId },
    {
      timeout: FINALIZE_TIMEOUT_MS,
      signal,
    },
  );
  return unwrapData(response);
}

export async function fetchSpeechAudio(audioUrl, signal) {
  const response = await api.get(audioUrl, {
    responseType: "blob",
    timeout: AUDIO_TIMEOUT_MS,
    signal,
  });
  const contentType = String(response.headers["content-type"] || "");
  if (contentType.includes("application/json")) {
    const parsed = JSON.parse(await response.data.text());
    const error = new Error(parsed.error?.message || "音频加载失败");
    error.apiError = parsed.error;
    error.userMessage = parsed.error?.message || "推荐语音加载失败，已保留文字推荐";
    throw error;
  }
  if (!(response.data instanceof Blob) || response.data.size === 0) {
    const error = new Error("音频为空");
    error.userMessage = "推荐语音加载失败，已保留文字推荐";
    throw error;
  }
  return response.data;
}
