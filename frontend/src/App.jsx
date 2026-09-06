import { useState } from "react";
import CitySelect from "./components/CitySelect.jsx";
import LocalPlayback from "./components/LocalPlayback.jsx";
import RecordButton from "./components/RecordButton.jsx";
import { useRecorder } from "./useRecorder.js";

export default function App() {
  const [city, setCity] = useState("杭州");
  const { status, message, result, startRecording, finishRecording, cancelRecording } =
    useRecorder();

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>
      <p>按住说话，系统会帮同一座城市里的两个人找中间的碰面店铺。</p>
      <CitySelect value={city} onChange={setCity} />
      <RecordButton
        status={status}
        onPressStart={startRecording}
        onPressEnd={finishRecording}
        onPressCancel={cancelRecording}
      />
      {message ? <p className="status">{message}</p> : null}
      {result ? <LocalPlayback result={result} /> : null}
      <p className="hint">本轮只做本地录音，不会识别文字或查找店铺。</p>
    </main>
  );
}
