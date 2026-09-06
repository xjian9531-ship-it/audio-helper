export default function RecordButton({ status, onPressStart, onPressEnd, onPressCancel }) {
  const handlePointerDown = (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    onPressStart();
  };

  const handlePointerUp = (event) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    onPressEnd();
  };

  const handlePointerCancel = () => {
    onPressCancel();
  };

  const handleContextMenu = (event) => {
    event.preventDefault();
  };

  const label = status === "recording" || status === "requesting" ? "正在录音" : "按住说话";

  return (
    <button
      type="button"
      className={`record-button${status === "recording" ? " is-recording" : ""}`}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
      onContextMenu={handleContextMenu}
    >
      {label}
    </button>
  );
}
