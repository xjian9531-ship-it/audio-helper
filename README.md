# 语音约碰面地点

按住说话，为同一座城市里的两个人推荐中间的碰面店铺。第一版只支持两个人、同一座城市。

页面按顺序完成：录音 → 上传 → 识别 → 提取 → 搜店 → 推荐语 → 尽量播报。店铺距离只表示「距离中点」，不表示两人出行时间相同。

当前进度：后端接口和前端联调代码已按约定接上，**尚未做完整验收，不能称为项目完成**。启动时清理超过 24 小时的临时文件尚未实现；读文件时仍会检查 24 小时有效期。

## 环境

- Python 3.11
- Node.js 22.12 及以上的 22.x
- ffprobe（随 FFmpeg 安装）。后端用它校验录音的真实容器、编码和时长，不做转码。Windows 可用 `winget install --id Gyan.FFmpeg -e`。安装后请新开终端，再启动后端。

后端端口 `8003`，前端端口 `5175`。请用 **http://localhost:5175** 打开页面。CORS 只放行该地址，不要用 `127.0.0.1:5175`。

推荐浏览器：支持 WebM/Opus 的 Chrome 或 Edge。

## 配置

外部服务密钥只放在 `backend/.env`，仓库只保留空值模板 `backend/.env.example`。不要提交 `.env`，也不要把密钥发给任何人。

从模板复制后自行填写：

```powershell
copy backend\.env.example backend\.env
```

需要填写的密钥：

- `BAILIAN_API_KEY`：百炼（北京），ASR 与 TTS 共用
- `DEEPSEEK_API_KEY`：提取与推荐语
- `AMAP_API_KEY`：高德 **Web 服务** Key，不是前端 JS Key

模型和完整 URL 已按确认方案写在模板里，一般不用改：

| 用途 | 配置项 |
|---|---|
| 识别 | `BAILIAN_ASR_URL`、`BAILIAN_ASR_MODEL=qwen3-asr-flash` |
| 语音合成 | `BAILIAN_TTS_URL`、`BAILIAN_TTS_MODEL=qwen3-tts-flash`、`BAILIAN_TTS_VOICE=Cherry` |
| 提取 / 推荐语 | `DEEPSEEK_CHAT_URL`、`DEEPSEEK_MODEL=deepseek-v4-flash` |
| 定位 / 搜店 | `AMAP_GEO_URL`、`AMAP_AROUND_URL` |

密钥未填时，`GET /health` 仍应返回成功。识别、提取、搜店、推荐语、TTS 的真实调用会失败。

临时文件写在 `backend/storage/`（录音、搜索结果、播报音频），已由 `.gitignore` 忽略。编号自创建起有效 24 小时，读取时检查过期。

## 启动

后端（在 `backend` 目录）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8003
```

前端（在 `frontend` 目录）：

```powershell
npm install
npm run dev
```

- 前端页面：http://localhost:5175
- 健康检查：http://localhost:8003/health
- 接口文档：http://localhost:8003/docs

页顶应显示「服务已连接」。改 `.env` 后需等后端 reload，或自行重启 uvicorn。

## 模拟测试

在 `backend` 目录、已激活虚拟环境后：

```powershell
python -m pytest
```

这些测试用 FastAPI `TestClient` 和 Mock，不访问百炼、DeepSeek、高德或 TTS。覆盖健康检查、上传、识别、提取、搜店、推荐语降级和音频接口的部分分支。

**Mock 通过不能代替真实接口联调，也不能证明前端全链路可用。**

前端没有自动化测试，页面行为需在浏览器里人工验收。

## 真实接口验收

填写三项真实密钥，并确认本机已有 ffprobe。真实调用会计费或占用配额，由你确认后执行。

建议顺序：

1. 浏览器打开 http://localhost:5175，确认健康检查。
2. 按住说话走完整链路，核对照片上的识别文字、提取信息、最多 3 家店和推荐语，并用返回的 `audio_url` 播放。不要用上传得到的 `rec_` 编号拼接播报地址。
3. 在开发者工具 Network 中核对待求顺序：`/health` → `/upload` → `/asr` → `/extract` → `/search` → `/finalize` → `/audio/tts_...`。
4. 再用接口文档或临时改 URL 检查业务失败、超时和文字降级。测完把配置改回。

详细逐步清单见验收时的对照表。未执行的项目不要标为通过。

## Git 忽略

不应提交：

- `backend/.env` 及任何真实密钥
- `backend/storage/` 下的录音、搜索结果和播报文件
- `backend/.venv/`、`__pycache__/`、`.pytest_cache/`
- `frontend/node_modules/`、`frontend/dist/`

可以提交：只含空值或安全占位符的 `backend/.env.example`。
