export default function HealthStatus({ status, message }) {
  const ok = status === "ok";
  return (
    <p className={`health${ok ? " is-ok" : " is-bad"}`}>
      {ok ? "服务已连接" : message || "正在检查服务"}
    </p>
  );
}
