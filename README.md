# 语音约碰面地点

按住说话，为同一座城市里的两个人推荐中间的碰面店铺。

当前进度：项目骨架。已提供后端 `GET /health` 和可打开的前端基础页。录音、识别、提取、搜店和语音播报尚未实现。

## 环境

- Python 3.11
- Node.js 22.12 及以上的 22.x

后端端口 `8003`，前端端口 `5175`。外部服务密钥放在 `backend/.env`，仓库只保留 `backend/.env.example`。密钥未填写时，健康检查仍应可用。

## 模拟测试

在 `backend` 目录安装依赖后执行：

```powershell
python -m pytest tests/test_health.py
```

该测试使用 FastAPI `TestClient`，不调用百炼、DeepSeek 或高德。Mock 通过不能证明真实外部服务已跑通。

## 真实接口验收

配置 `backend/.env` 中的 `BAILIAN_API_KEY`、`DEEPSEEK_API_KEY`、`AMAP_API_KEY` 后，再按后续接口说明做人工验收。当前骨架没有这些调用，也无需为健康检查填写密钥。

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
