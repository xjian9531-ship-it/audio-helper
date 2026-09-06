import { useCallback, useEffect, useState } from "react";
import { checkHealth, isCanceledError, toUserMessage } from "./api.js";
import CitySelect from "./components/CitySelect.jsx";
import HealthStatus from "./components/HealthStatus.jsx";
import LocalPlayback from "./components/LocalPlayback.jsx";
import MeetupResult from "./components/MeetupResult.jsx";
import RecordButton from "./components/RecordButton.jsx";
import { useMeetup } from "./useMeetup.js";
import { useRecorder } from "./useRecorder.js";

export default function App() {
  const [city, setCity] = useState("杭州");
  const [healthStatus, setHealthStatus] = useState("");
  const [healthMessage, setHealthMessage] = useState("正在检查服务");
  const meetup = useMeetup();

  const handleSessionStart = useCallback(() => {
    meetup.abortInFlight();
  }, [meetup.abortInFlight]);

  const handleReady = useCallback(
    (recording) => {
      meetup.startPipeline(recording.blob, city);
    },
    [city, meetup.startPipeline],
  );

  const { status, message, result, startRecording, finishRecording, cancelRecording } =
    useRecorder({
      onSessionStart: handleSessionStart,
      onReady: handleReady,
    });

  useEffect(() => {
    const controller = new AbortController();
    checkHealth(controller.signal)
      .then((data) => {
        setHealthStatus(data.status);
        setHealthMessage(data.status === "ok" ? "服务已连接" : "服务未就绪");
      })
      .catch((error) => {
        if (isCanceledError(error)) {
          return;
        }
        setHealthStatus("");
        setHealthMessage(toUserMessage(error, "服务未就绪"));
      });
    return () => controller.abort();
  }, []);

  const recording = status === "recording" || status === "requesting";
  const statusLine = recording
    ? message
    : meetup.stageLabel || meetup.errorMessage || message;

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>
      <p>按住说话，系统会帮同一座城市里的两个人找中间的碰面店铺。</p>
      <HealthStatus status={healthStatus} message={healthMessage} />
      <CitySelect value={city} onChange={setCity} />
      <RecordButton
        status={status}
        onPressStart={startRecording}
        onPressEnd={finishRecording}
        onPressCancel={cancelRecording}
      />
      {statusLine ? <p className="status">{statusLine}</p> : null}
      {result ? <LocalPlayback result={result} /> : null}
      <MeetupResult result={meetup.result} onPlay={meetup.playSpeech} />
    </main>
  );
}
