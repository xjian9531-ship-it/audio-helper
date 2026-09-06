import { useCallback, useEffect, useRef, useState } from "react";
import {
  extractMeetup,
  fetchSpeechAudio,
  finalizeMeetup,
  isCanceledError,
  recognizeAudio,
  searchMeetup,
  toUserMessage,
  uploadRecording,
} from "./api.js";

const STAGE_LABELS = {
  upload: "上传中",
  asr: "识别中",
  extract: "提取中",
  search: "找店中",
  finalize: "生成推荐中",
};

function emptyResult() {
  return {
    transcript: "",
    extract: null,
    pois: [],
    replyText: "",
    warning: "",
    audioUrl: null,
    speechObjectUrl: "",
    needManualPlay: false,
  };
}

export function useMeetup() {
  const [stage, setStage] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [result, setResult] = useState(emptyResult);

  const runIdRef = useRef(0);
  const abortRef = useRef(null);
  const audioRef = useRef(null);
  const speechUrlRef = useRef("");
  const busyRef = useRef(false);

  const stopSpeech = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.removeAttribute("src");
      audioRef.current.load();
      audioRef.current = null;
    }
    if (speechUrlRef.current) {
      URL.revokeObjectURL(speechUrlRef.current);
      speechUrlRef.current = "";
    }
  }, []);

  const abortInFlight = useCallback(() => {
    runIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    busyRef.current = false;
    stopSpeech();
    setBusy(false);
    setStage("");
  }, [stopSpeech]);

  const playSpeech = useCallback(async () => {
    if (!audioRef.current) {
      return;
    }
    try {
      await audioRef.current.play();
      setResult((prev) => ({ ...prev, needManualPlay: false }));
    } catch {
      setResult((prev) => ({ ...prev, needManualPlay: true }));
    }
  }, []);

  const startPipeline = useCallback(
    async (blob, city) => {
      const trimmedCity = String(city || "").trim();
      if (!trimmedCity) {
        setErrorMessage("请填写城市");
        setBusy(false);
        setStage("");
        return;
      }

      abortRef.current?.abort();
      stopSpeech();
      const runId = runIdRef.current + 1;
      runIdRef.current = runId;
      const controller = new AbortController();
      abortRef.current = controller;
      busyRef.current = true;

      setBusy(true);
      setErrorMessage("");
      setResult(emptyResult());

      const stillCurrent = () => runId === runIdRef.current;

      try {
        setStage("upload");
        const uploaded = await uploadRecording(blob, controller.signal);
        if (!stillCurrent()) {
          return;
        }

        setStage("asr");
        const asr = await recognizeAudio(uploaded.audio_id, controller.signal);
        if (!stillCurrent()) {
          return;
        }
        setResult((prev) => ({ ...prev, transcript: asr.text }));

        setStage("extract");
        const extract = await extractMeetup(asr.text, trimmedCity, controller.signal);
        if (!stillCurrent()) {
          return;
        }
        setResult((prev) => ({ ...prev, transcript: asr.text, extract }));

        setStage("search");
        const search = await searchMeetup(extract, controller.signal);
        if (!stillCurrent()) {
          return;
        }
        setResult((prev) => ({
          ...prev,
          transcript: asr.text,
          extract,
          pois: Array.isArray(search.pois) ? search.pois : [],
        }));

        setStage("finalize");
        const finalized = await finalizeMeetup(search.search_id, controller.signal);
        if (!stillCurrent()) {
          return;
        }
        setResult((prev) => ({
          ...prev,
          transcript: asr.text,
          extract,
          pois: Array.isArray(search.pois) ? search.pois : [],
          replyText: finalized.reply_text,
          warning: finalized.warning || "",
          audioUrl: finalized.audio_url,
        }));

        if (finalized.audio_url) {
          try {
            const speechBlob = await fetchSpeechAudio(finalized.audio_url, controller.signal);
            if (!stillCurrent()) {
              return;
            }
            const objectUrl = URL.createObjectURL(speechBlob);
            speechUrlRef.current = objectUrl;
            const audio = new Audio(objectUrl);
            audioRef.current = audio;
            setResult((prev) => ({ ...prev, speechObjectUrl: objectUrl }));
            try {
              await audio.play();
              if (!stillCurrent()) {
                return;
              }
              setResult((prev) => ({
                ...prev,
                needManualPlay: false,
                speechObjectUrl: objectUrl,
              }));
            } catch {
              if (!stillCurrent()) {
                return;
              }
              setResult((prev) => ({
                ...prev,
                needManualPlay: true,
                speechObjectUrl: objectUrl,
              }));
            }
          } catch (audioError) {
            if (isCanceledError(audioError) || !stillCurrent()) {
              return;
            }
            setResult((prev) => ({
              ...prev,
              warning: prev.warning || toUserMessage(audioError, "推荐语音加载失败，已保留文字推荐"),
            }));
          }
        }

        if (stillCurrent()) {
          setStage("");
          setBusy(false);
          busyRef.current = false;
        }
      } catch (error) {
        if (isCanceledError(error) || !stillCurrent()) {
          return;
        }
        setErrorMessage(toUserMessage(error, "请求失败，请稍后重试"));
        setBusy(false);
        busyRef.current = false;
        setStage("");
      }
    },
    [stopSpeech],
  );

  useEffect(
    () => () => {
      abortInFlight();
    },
    [abortInFlight],
  );

  return {
    stage,
    stageLabel: STAGE_LABELS[stage] || "",
    busy,
    errorMessage,
    result,
    abortInFlight,
    startPipeline,
    playSpeech,
  };
}
