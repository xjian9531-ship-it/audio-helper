import { useCallback, useEffect, useRef, useState } from "react";
import {
  MAX_DURATION_MS,
  MAX_FILE_BYTES,
  MIN_DURATION_MS,
  describeRecordError,
  detectSupportedMimeType,
} from "./recording.js";

function stopTracks(stream) {
  if (!stream) {
    return;
  }
  for (const track of stream.getTracks()) {
    track.stop();
  }
}

export function useRecorder() {
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState(null);

  const sessionRef = useRef(0);
  const phaseRef = useRef("idle");
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const startedAtRef = useRef(0);
  const mimeTypeRef = useRef("");
  const maxTimerRef = useRef(0);
  const objectUrlRef = useRef("");

  const clearMaxTimer = useCallback(() => {
    if (maxTimerRef.current) {
      window.clearTimeout(maxTimerRef.current);
      maxTimerRef.current = 0;
    }
  }, []);

  const revokeObjectUrl = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = "";
    }
  }, []);

  const releaseMicrophone = useCallback(() => {
    stopTracks(streamRef.current);
    streamRef.current = null;
  }, []);

  const resetResult = useCallback(() => {
    revokeObjectUrl();
    setResult(null);
  }, [revokeObjectUrl]);

  const finalizeBlob = useCallback(
    (reason) => {
      const durationMs = Date.now() - startedAtRef.current;
      const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
      chunksRef.current = [];
      recorderRef.current = null;
      releaseMicrophone();
      phaseRef.current = "idle";

      if (reason === "cancel") {
        setStatus("idle");
        setMessage("已取消录音");
        return;
      }

      if (durationMs < MIN_DURATION_MS || durationMs > MAX_DURATION_MS + 500) {
        setStatus("error");
        setMessage("录音时长需在 1 到 60 秒之间");
        return;
      }

      if (blob.size > MAX_FILE_BYTES) {
        setStatus("error");
        setMessage("录音文件过大，请控制在 5MB 以内");
        return;
      }

      if (blob.size === 0) {
        setStatus("error");
        setMessage("录制失败，请重试");
        return;
      }

      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      setResult({
        url,
        blob,
        mimeType: blob.type || mimeTypeRef.current,
        durationMs,
        sizeBytes: blob.size,
      });
      setStatus("ready");
      setMessage("录音完成，可以试听或下载");
    },
    [releaseMicrophone],
  );

  const stopRecorder = useCallback(
    (reason) => {
      clearMaxTimer();
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        releaseMicrophone();
        phaseRef.current = "idle";
        if (reason === "cancel") {
          setStatus("idle");
          setMessage("已取消录音");
        }
        return;
      }

      phaseRef.current = "stopping";

      recorder.onstop = () => {
        finalizeBlob(reason);
      };
      recorder.stop();
    },
    [clearMaxTimer, finalizeBlob, releaseMicrophone],
  );

  const cancelRecording = useCallback(() => {
    if (phaseRef.current === "idle") {
      return;
    }
    sessionRef.current += 1;
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      stopRecorder("cancel");
      return;
    }
    clearMaxTimer();
    releaseMicrophone();
    phaseRef.current = "idle";
    setStatus("idle");
    setMessage("已取消录音");
  }, [clearMaxTimer, releaseMicrophone, stopRecorder]);

  const startRecording = useCallback(async () => {
    const mimeType = detectSupportedMimeType();
    if (!mimeType) {
      phaseRef.current = "idle";
      setStatus("error");
      setMessage("当前浏览器不支持 WebM/Opus 录音，请更换浏览器");
      return;
    }

    if (phaseRef.current !== "idle") {
      return;
    }

    const session = sessionRef.current + 1;
    sessionRef.current = session;
    phaseRef.current = "requesting";
    resetResult();
    setStatus("requesting");
    setMessage("正在请求麦克风");

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      if (session !== sessionRef.current) {
        return;
      }
      phaseRef.current = "idle";
      setStatus("error");
      setMessage(describeRecordError(error));
      return;
    }

    if (session !== sessionRef.current || phaseRef.current !== "requesting") {
      stopTracks(stream);
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];
    mimeTypeRef.current = mimeType;

    try {
      const recorder = new MediaRecorder(stream, { mimeType });
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onerror = () => {
        if (session !== sessionRef.current) {
          return;
        }
        clearMaxTimer();
        releaseMicrophone();
        recorderRef.current = null;
        phaseRef.current = "idle";
        setStatus("error");
        setMessage("录制失败，请重试");
      };
      recorderRef.current = recorder;
      recorder.start();
      startedAtRef.current = Date.now();
      phaseRef.current = "recording";
      setStatus("recording");
      setMessage("正在录音");
      maxTimerRef.current = window.setTimeout(() => {
        if (session !== sessionRef.current) {
          return;
        }
        stopRecorder("complete");
      }, MAX_DURATION_MS);
    } catch (error) {
      stopTracks(stream);
      streamRef.current = null;
      if (session !== sessionRef.current) {
        return;
      }
      phaseRef.current = "idle";
      setStatus("error");
      setMessage(describeRecordError(error));
    }
  }, [clearMaxTimer, releaseMicrophone, resetResult, stopRecorder]);

  const finishRecording = useCallback(() => {
    if (phaseRef.current === "requesting") {
      sessionRef.current += 1;
      phaseRef.current = "idle";
      releaseMicrophone();
      setStatus("error");
      setMessage("录音时长需在 1 到 60 秒之间");
      return;
    }

    if (phaseRef.current !== "recording") {
      return;
    }

    stopRecorder("complete");
  }, [releaseMicrophone, stopRecorder]);

  useEffect(() => {
    const onHidden = () => {
      if (document.visibilityState === "hidden" && phaseRef.current !== "idle") {
        cancelRecording();
      }
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        cancelRecording();
      }
    };

    document.addEventListener("visibilitychange", onHidden);
    window.addEventListener("pagehide", onHidden);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("visibilitychange", onHidden);
      window.removeEventListener("pagehide", onHidden);
      window.removeEventListener("keydown", onKeyDown);
      sessionRef.current += 1;
      clearMaxTimer();
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.onstop = null;
        recorderRef.current.stop();
      }
      recorderRef.current = null;
      releaseMicrophone();
      revokeObjectUrl();
    };
  }, [cancelRecording, clearMaxTimer, releaseMicrophone, revokeObjectUrl]);

  return {
    status,
    message,
    result,
    startRecording,
    finishRecording,
    cancelRecording,
  };
}
