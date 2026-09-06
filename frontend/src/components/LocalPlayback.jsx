function formatDuration(durationMs) {
  return `${(durationMs / 1000).toFixed(1)} 秒`;
}

function formatSize(sizeBytes) {
  if (sizeBytes >= 1024 * 1024) {
    return `${(sizeBytes / (1024 * 1024)).toFixed(2)} MB`;
  }
  return `${(sizeBytes / 1024).toFixed(1)} KB`;
}

export default function LocalPlayback({ result }) {
  const filename = "recording.webm";

  return (
    <section className="local-playback">
      <h2>本轮录音</h2>
      <audio controls src={result.url} />
      <p>
        格式 {result.mimeType}，时长 {formatDuration(result.durationMs)}，大小{" "}
        {formatSize(result.sizeBytes)}
      </p>
      <a className="download-link" href={result.url} download={filename}>
        下载录音文件
      </a>
    </section>
  );
}
