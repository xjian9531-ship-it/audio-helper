function formatDistance(meters) {
  const value = Number(meters);
  if (!Number.isFinite(value)) {
    return "距离中点未知";
  }
  const text = Number.isInteger(value) ? String(value) : value.toFixed(1);
  return `距离中点 ${text} 米`;
}

export default function MeetupResult({ result, onPlay }) {
  const { transcript, extract, pois, replyText, warning, speechObjectUrl, needManualPlay } =
    result;
  const hasExtract = Boolean(extract);
  const hasPois = Array.isArray(pois) && pois.length > 0;
  const hasReply = Boolean(replyText);

  if (!transcript && !hasExtract && !hasPois && !hasReply) {
    return null;
  }

  return (
    <section className="meetup-result">
      {transcript ? (
        <div className="result-block">
          <h2>识别文字</h2>
          <p>{transcript}</p>
        </div>
      ) : null}

      {hasExtract ? (
        <div className="result-block">
          <h2>提取信息</h2>
          <p>
            {extract.city_a} {extract.address_a}
          </p>
          <p>
            {extract.city_b} {extract.address_b}
          </p>
          <p>类别：{extract.category}</p>
        </div>
      ) : null}

      {hasPois ? (
        <div className="result-block">
          <h2>候选店铺</h2>
          <ol className="poi-list">
            {pois.slice(0, 3).map((poi, index) => (
              <li key={`${poi.name}-${poi.address}-${index}`}>
                <strong>{poi.name}</strong>
                <span>{poi.address}</span>
                <span>{formatDistance(poi.distance_to_midpoint_m)}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {hasReply ? (
        <div className="result-block">
          <h2>推荐语</h2>
          <p>{replyText}</p>
          {warning ? <p className="warning">{warning}</p> : null}
          {speechObjectUrl ? <audio controls src={speechObjectUrl} /> : null}
          {needManualPlay ? (
            <button type="button" className="play-button" onClick={onPlay}>
              播放推荐语音
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
