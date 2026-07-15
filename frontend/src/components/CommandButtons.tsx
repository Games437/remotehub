import { useEffect, useState } from "react";
import {
  useSendCommand,
  useCommand,
  useCommandHistory,
  usePurgeCommandResult,
  HISTORY_PAGE_SIZE,
} from "../hooks/useMachines";

type Category = "actions" | "status" | "power";

const CATEGORIES: { key: Category; label: string }[] = [
  { key: "actions", label: "Actions" },
  { key: "status", label: "Status" },
  { key: "power", label: "Power" },
];

const ACTIONS: {
  type: string;
  label: string;
  category: Category;
  needsPayload?: "url" | "path" | "pid" | "message";
  needsConfirm?: boolean;
}[] = [
  { type: "open_website", label: "Open website", category: "actions", needsPayload: "url" },
  { type: "open_program", label: "Open program", category: "actions", needsPayload: "path" },
  { type: "send_message", label: "Send message", category: "actions", needsPayload: "message" },
  { type: "screenshot", label: "Screenshot", category: "actions" },
  { type: "get_idle_time", label: "Idle time", category: "status" },
  { type: "list_processes", label: "Processes", category: "status" },
  { type: "get_active_window", label: "Active window", category: "status" },
  { type: "list_open_windows", label: "Open windows", category: "status" },
  { type: "get_network_status", label: "Network status", category: "status" },
  { type: "get_system_info", label: "System info", category: "status" },
  { type: "lock", label: "Lock", category: "power", needsConfirm: true },
  { type: "sleep", label: "Sleep", category: "power", needsConfirm: true },
  { type: "restart", label: "Restart", category: "power", needsConfirm: true },
  { type: "shutdown", label: "Shutdown", category: "power", needsConfirm: true },
  {
    type: "kill_process",
    label: "Kill process",
    category: "power",
    needsPayload: "pid",
    needsConfirm: true,
  },
];

// These commands just report back data (no side effect on the machine), so
// they get toggle behavior: click once to run + show, click the same
// button again to collapse instead of re-running it.
const QUERY_TYPES = new Set([
  "get_idle_time",
  "list_processes",
  "get_active_window",
  "list_open_windows",
  "get_network_status",
  "get_system_info",
]);

const SHUTDOWN_GRACE_SECONDS = 60;

// Copy + behavior for the confirm modal, per command. Only shutdown/restart
// get the grace-period + cancel-window treatment — lock/sleep are instant
// once confirmed, since there's no "undo" for them once sent, but there's
// also nothing to warn the person at the keyboard about in advance.
const CONFIRM_COPY: Record<
  string,
  { verb: string; hasGracePeriod: boolean; subject?: (payload?: Record<string, unknown>) => string }
> = {
  shutdown: { verb: "ปิดเครื่อง", hasGracePeriod: true },
  restart: { verb: "รีสตาร์ท", hasGracePeriod: true },
  lock: { verb: "ล็อกหน้าจอ", hasGracePeriod: false },
  sleep: { verb: "พักเครื่อง (sleep)", hasGracePeriod: false },
  kill_process: {
    verb: "ปิดโปรแกรม",
    hasGracePeriod: false,
    subject: (payload) => `process PID ${payload?.pid ?? "?"} บน`,
  },
};
const RECENTS_KEY_PREFIX = "remotehub:recents:";
const MAX_RECENTS = 5;

function loadRecents(kind: "url" | "path" | "message"): string[] {
  try {
    const raw = localStorage.getItem(RECENTS_KEY_PREFIX + kind);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function saveRecent(kind: "url" | "path" | "message", value: string) {
  const existing = loadRecents(kind).filter((v) => v !== value);
  const updated = [value, ...existing].slice(0, MAX_RECENTS);
  localStorage.setItem(RECENTS_KEY_PREFIX + kind, JSON.stringify(updated));
}

function downloadBase64(base64: string, format: string, filename: string) {
  fetch(`data:image/${format};base64,${base64}`)
    .then((res) => res.blob())
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    })
    .catch((err) => console.error("Blob generation failed:", err));
}

interface PayloadModalState {
  type: string;
  label: string;
  kind: "url" | "path" | "pid" | "message";
  // Carried over from the action definition — if set, submitting this
  // modal doesn't dispatch immediately, it opens the confirm modal next
  // (e.g. kill_process: pick a PID, then confirm before actually sending).
  needsConfirm?: boolean;
}

interface ConfirmModalState {
  type: string;
  label: string;
  payload?: Record<string, unknown>;
}

export default function CommandButtons({
  machineId,
  online,
}: {
  machineId: string;
  online: boolean;
}) {
  const sendCommand = useSendCommand(machineId);
  const purgeResult = usePurgeCommandResult(machineId);

  const [pendingType, setPendingType] = useState<string | null>(null);
  const [activeCommandId, setActiveCommandId] = useState<string | null>(null);

  const [payloadModal, setPayloadModal] = useState<PayloadModalState | null>(null);
  const [confirmModal, setConfirmModal] = useState<ConfirmModalState | null>(null);
  const [inputValue, setInputValue] = useState("");

  // Persisted separately from activeCommandId so they don't vanish the
  // instant the effect below resets activeCommandId back to null.
  const [lastFailure, setLastFailure] = useState<{
    commandType: string;
    error?: string;
    debugScreenshot?: { base64: string; format: string };
  } | null>(null);
  const [queryResult, setQueryResult] = useState<{
    commandType: string;
    data: Record<string, unknown>;
  } | null>(null);
  const [shutdownPending, setShutdownPending] = useState<"shutdown" | "restart" | null>(null);
  const [shutdownDeadline, setShutdownDeadline] = useState<number | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [activeTab, setActiveTab] = useState<Category>("actions");

  // Live countdown while a shutdown/restart is pending — ticks every
  // second purely on the client; the actual cutoff is enforced by the OS
  // (`shutdown /t N`) on the agent's side regardless of this UI.
  useEffect(() => {
    if (!shutdownDeadline) return;
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((shutdownDeadline - Date.now()) / 1000));
      setSecondsLeft(remaining);
      if (remaining === 0) {
        // Deadline passed — the OS-level shutdown/restart has already
        // fired, so "Cancel" no longer means anything. Clear it instead
        // of leaving a dead button showing "0s left" forever.
        setShutdownPending(null);
        setShutdownDeadline(null);
      }
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [shutdownDeadline]);

  // History panel is a separate toggle from queryResult — it's a local UI
  // view of past commands, not a command sent to the agent.
  const [showHistory, setShowHistory] = useState(false);
  const [historyPage, setHistoryPage] = useState(0);
  const history = useCommandHistory(machineId, historyPage, showHistory);

  const { data: activeCommand } = useCommand(machineId, activeCommandId);

  useEffect(() => {
    if (!activeCommand) return;

    if (
      activeCommand.status !== "acknowledged" &&
      activeCommand.status !== "failed"
    ) {
      return;
    }

    if (activeCommand.status === "failed") {
      const result = activeCommand.result as
        | {
            error?: string;
            debug_screenshot_b64?: string;
            debug_screenshot_format?: string;
          }
        | null;
      setLastFailure({
        commandType: activeCommand.command_type,
        error: result?.error ? String(result.error) : undefined,
        debugScreenshot: result?.debug_screenshot_b64
          ? { base64: result.debug_screenshot_b64, format: result.debug_screenshot_format || "png" }
          : undefined,
      });
    } else if (activeCommand.status === "acknowledged") {
      setLastFailure(null);
      const result = activeCommand.result as Record<string, unknown> | null;
      const type = activeCommand.command_type;

      if (type === "screenshot" && result?.image_b64) {
        try {
          const format = (result.format as string) ?? "png";
          downloadBase64(
            result.image_b64 as string,
            format,
            `screenshot-${machineId}-${Date.now()}.${format}`
          );
          purgeResult.mutate(activeCommand.id, {
            onError: (err) => console.error("Failed to purge screenshot:", err),
          });
        } catch (err) {
          console.error("Failed to download screenshot:", err);
        }
      } else if (QUERY_TYPES.has(type)) {
        // Single source of truth with the toggle-behavior set above —
        // forgetting to add a new query command to *both* places was
        // exactly the bug that made get_system_info silently show nothing.
        setQueryResult({ commandType: type, data: result || {} });
      } else if (type === "send_message" || type === "kill_process") {
        // One-shot actions that still deserve visible confirmation — unlike
        // lock/sleep, "did that actually work" isn't obvious from the UI
        // otherwise. Reuses the same result panel/Close button as queries,
        // just isn't wired into the toggle set since re-clicking should
        // resend, not collapse a stale confirmation.
        setQueryResult({ commandType: type, data: result || {} });
      } else if (type === "shutdown" || type === "restart") {
        setShutdownPending(type);
        setShutdownDeadline(Date.now() + SHUTDOWN_GRACE_SECONDS * 1000);
      } else if (type === "cancel_shutdown") {
        setShutdownPending(null);
        setShutdownDeadline(null);
      }
    }

    setActiveCommandId(null);
    setPendingType(null);
  }, [activeCommand, machineId, purgeResult]);

  // ฟังก์ชันยิงคำสั่งจริง (เดิมชื่อ run แยกออกมาเป็น dispatch เพื่อให้
  // ทั้ง modal กรอกข้อมูล และ modal ยืนยัน เรียกใช้ร่วมกันได้)
  function dispatch(type: string, payload?: Record<string, unknown>) {
    setLastFailure(null);
    setPendingType(type);

    sendCommand.mutate(
      { command_type: type, payload },
      {
        onSuccess: (data) => setActiveCommandId(data.id),
        onError: () => setPendingType(null),
      }
    );
  }

  // จุดตัดสินใจตอนกดปุ่ม: ต้องกรอกข้อมูลก่อนไหม / ต้องยืนยันก่อนไหม / ยิงเลย
  function handleActionClick(action: (typeof ACTIONS)[number]) {
    // Query-type commands (idle time, processes, etc.) toggle: clicking the
    // same button again while its result is already showing just collapses
    // it, rather than sending the command to the agent a second time.
    if (QUERY_TYPES.has(action.type) && queryResult?.commandType === action.type) {
      setQueryResult(null);
      return;
    }
    if (action.needsPayload) {
      setInputValue("");
      setPayloadModal({
        type: action.type,
        label: action.label,
        kind: action.needsPayload,
        needsConfirm: action.needsConfirm,
      });
      return;
    }
    if (action.needsConfirm) {
      setConfirmModal({ type: action.type, label: action.label });
      return;
    }
    dispatch(action.type);
  }

  function submitPayloadModal() {
    if (!payloadModal || !inputValue.trim()) return;
    const value = inputValue.trim();
    const key = payloadModal.kind;

    if (key !== "pid") saveRecent(key, value); // a PID is never worth remembering
    const payload = { [key]: key === "pid" ? Number(value) : value };

    if (payloadModal.needsConfirm) {
      // e.g. kill_process — the PID is picked here, but actually sending
      // it still goes through the confirm step, carrying the payload along.
      setConfirmModal({ type: payloadModal.type, label: payloadModal.label, payload });
      setPayloadModal(null);
      return;
    }
    dispatch(payloadModal.type, payload);
    setPayloadModal(null);
  }

  // เรียกจากปุ่ม Kill ในตาราง Processes — ถ้ามี instance เดียวข้ามการพิมพ์ PID
  // เองไปเลย เข้า confirm modal ตรง; ถ้ามีหลาย instance เติม PID ตัวแรกให้ในช่อง
  // กรอกแทน (ยังแก้ไขเป็นตัวอื่นในกลุ่มเดียวกันได้ถ้าต้องการ)
  function handleKillFromProcessRow(pids: number[]) {
    if (pids.length === 1) {
      setConfirmModal({ type: "kill_process", label: "Kill process", payload: { pid: pids[0] } });
      return;
    }
    setInputValue(String(pids[0]));
    setPayloadModal({ type: "kill_process", label: "Kill process", kind: "pid", needsConfirm: true });
  }

  function confirmDangerousAction() {
    if (!confirmModal) return;
    if (CONFIRM_COPY[confirmModal.type]?.hasGracePeriod) {
      // Shutdown/restart always go out with a grace period + local
      // notification — the agent warns whoever's at the keyboard and
      // gives them time to cancel, since the operator sending this has no
      // live view of the screen.
      dispatch(confirmModal.type, { delay_seconds: SHUTDOWN_GRACE_SECONDS });
    } else {
      // Lock/sleep/kill_process have no grace period concept — confirm
      // just guards against an accidental click, then it's sent right
      // away, carrying whatever payload (e.g. pid) was collected earlier.
      dispatch(confirmModal.type, confirmModal.payload);
    }
    setConfirmModal(null);
  }

  const isBusy = (type: string) =>
    pendingType === type &&
    (sendCommand.isPending ||
      (activeCommand?.status !== "acknowledged" &&
        activeCommand?.status !== "failed"));

  return (
    <div>
      <div className="flex gap-1 mb-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            onClick={() => setActiveTab(cat.key)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition ${
              activeTab === cat.key
                ? "border-accent bg-accent/10 text-accent"
                : "border-line bg-base text-muted hover:border-accent"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {ACTIONS.filter((action) => action.category === activeTab).map((action) => (
          <button
            key={action.type}
            disabled={!online || isBusy(action.type)}
            onClick={() => handleActionClick(action)}
            className="text-sm px-3 py-1.5 rounded-lg border border-line bg-base hover:border-accent
              disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {isBusy(action.type)
              ? sendCommand.isPending
                ? "Sending..."
                : "Waiting for agent..."
              : action.label}
          </button>
        ))}

        {shutdownPending && (
          <button
            disabled={!online || isBusy("cancel_shutdown")}
            onClick={() => dispatch("cancel_shutdown")}
            className="text-sm px-3 py-1.5 rounded-lg border border-red-500 text-red-500 bg-base hover:bg-red-500/10 disabled:opacity-40 transition"
          >
            {isBusy("cancel_shutdown")
              ? "Cancelling..."
              : `Cancel ${shutdownPending} (${secondsLeft}s left)`}
          </button>
        )}

        <button
          onClick={() => {
            // Toggle, same pattern as the query-type command buttons above.
            setShowHistory((s) => !s);
            setHistoryPage(0);
          }}
          className="text-sm px-3 py-1.5 rounded-lg border border-line bg-base hover:border-accent transition"
        >
          {showHistory ? "Hide history" : "History"}
        </button>
      </div>

      {lastFailure && (
        <div className="mt-2">
          <p className="text-sm text-red-500">
            Command failed ({lastFailure.commandType})
            {lastFailure.error ? `: ${lastFailure.error}` : ""}
          </p>
          {lastFailure.debugScreenshot && (
            <button
              className="text-xs text-accent underline mt-1"
              onClick={() =>
                downloadBase64(
                  lastFailure.debugScreenshot!.base64,
                  lastFailure.debugScreenshot!.format,
                  `debug-${machineId}-${Date.now()}.${lastFailure.debugScreenshot!.format}`
                )
              }
            >
              Download screen at time of failure
            </button>
          )}
        </div>
      )}

      {showHistory && (
        <div className="mt-2 text-sm bg-base border border-line rounded-lg p-3">
          {history.isLoading ? (
            <p className="text-muted">Loading...</p>
          ) : history.isError ? (
            <p className="text-red-500">Failed to load history.</p>
          ) : (
            <>
              <table className="w-full text-xs" style={{ tableLayout: "fixed" }}>
                <thead>
                  <tr className="text-muted">
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "35%" }}>Command</th>
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "20%" }}>Status</th>
                    <th className="text-left font-normal py-1" style={{ width: "45%" }}>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {history.data?.commands.map((c) => (
                    <tr key={c.id} className="border-t border-line">
                      <td className="py-1 pr-2 truncate">{c.command_type}</td>
                      <td className="py-1 pr-2">
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-md ${
                            c.status === "acknowledged"
                              ? "bg-green-500/15 text-green-500"
                              : c.status === "failed"
                              ? "bg-red-500/15 text-red-500"
                              : "bg-base text-muted"
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="py-1 mono text-muted">
                        {new Date(c.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                  {history.data?.commands.length === 0 && (
                    <tr>
                      <td colSpan={3} className="py-2 text-muted">
                        No commands sent to this machine yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              <div className="flex items-center justify-between mt-2">
                <button
                  disabled={historyPage === 0}
                  onClick={() => setHistoryPage((p) => Math.max(0, p - 1))}
                  className="text-xs text-muted hover:text-text disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  Prev
                </button>
                <span className="text-xs text-muted">
                  Page {historyPage + 1} of{" "}
                  {Math.max(1, Math.ceil((history.data?.total ?? 0) / HISTORY_PAGE_SIZE))}
                </span>
                <button
                  disabled={(historyPage + 1) * HISTORY_PAGE_SIZE >= (history.data?.total ?? 0)}
                  onClick={() => setHistoryPage((p) => p + 1)}
                  className="text-xs text-muted hover:text-text disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {queryResult && (
        <div className="mt-2 text-sm bg-base border border-line rounded-lg p-3 max-h-56 overflow-auto">
          {queryResult.commandType === "get_idle_time" && (
            <p>
              Idle for <span className="mono">{queryResult.data.idle_seconds as number}</span> seconds
            </p>
          )}
          {queryResult.commandType === "list_processes" && (
            <>
              <p className="text-muted mb-1">
                Top processes by memory ({(queryResult.data.total_count as number) ?? 0} total running,{" "}
                {(queryResult.data.grouped_count as number) ?? 0} shown grouped)
              </p>
              <table className="w-full text-xs" style={{ tableLayout: "fixed" }}>
                <thead>
                  <tr className="text-muted">
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "45%" }}>Program</th>
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "18%" }}>Memory</th>
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "17%" }}>CPU</th>
                    <th className="text-left font-normal py-1" style={{ width: "20%" }}></th>
                  </tr>
                </thead>
                <tbody>
                  {(queryResult.data.processes as Array<Record<string, unknown>> | undefined)?.map((p) => {
                    const pids = (p.pids as number[] | undefined) ?? [];
                    return (
                      <tr key={p.name as string} className="border-t border-line">
                        <td className="py-1 pr-2 truncate" title={p.name as string}>
                          {p.name as string}
                          {(p.instance_count as number) > 1 ? (
                            <span className="text-muted"> (×{p.instance_count as number})</span>
                          ) : null}
                        </td>
                        <td className="py-1 pr-2 mono">{(p.memory_percent as number).toFixed(1)}%</td>
                        <td className="py-1 pr-2 mono">{(p.cpu_percent as number).toFixed(1)}%</td>
                        <td className="py-1">
                          {pids.length > 0 && (
                            <button
                              onClick={() => handleKillFromProcessRow(pids)}
                              className="text-[11px] px-2 py-0.5 rounded-md border border-danger text-danger hover:bg-danger/10 transition"
                              title={`PID${pids.length > 1 ? "s" : ""}: ${pids.join(", ")}`}
                            >
                              Kill
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
          {queryResult.commandType === "get_active_window" && (
            <p>
              Focused: <span className="mono">{(queryResult.data.title as string) || "(none)"}</span>
              {queryResult.data.process_name ? (
                <span className="text-muted"> — {queryResult.data.process_name as string}</span>
              ) : null}
            </p>
          )}
          {queryResult.commandType === "list_open_windows" && (
            <>
              <p className="text-muted mb-1">
                Open windows ({(queryResult.data.total_count as number) ?? 0} total)
              </p>
              <table className="w-full text-xs" style={{ tableLayout: "fixed" }}>
                <thead>
                  <tr className="text-muted">
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "50%" }}>Window</th>
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "25%" }}>Program</th>
                    <th className="text-left font-normal py-1" style={{ width: "25%" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(queryResult.data.windows as Array<Record<string, unknown>> | undefined)?.map((w, i) => (
                    <tr key={i} className="border-t border-line">
                      <td
                        className="py-1 pr-2 truncate whitespace-nowrap overflow-hidden"
                        title={w.title as string}
                      >
                        {w.title as string}
                      </td>
                      <td className="py-1 pr-2 text-muted truncate whitespace-nowrap overflow-hidden">
                        {w.process_name as string}
                      </td>
                      <td className="py-1">
                        {w.minimized ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-base text-muted">
                            minimized
                          </span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-green-500/15 text-green-500">
                            visible
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {queryResult.commandType === "get_network_status" && (
            <p>
              {queryResult.data.connected ? "Connected" : "Disconnected"}
              {queryResult.data.connected && queryResult.data.latency_ms != null
                ? ` — ${queryResult.data.latency_ms as number}ms latency`
                : ""}
              {queryResult.data.interface ? (
                <span className="text-muted"> ({queryResult.data.interface as string})</span>
              ) : null}
            </p>
          )}
          {queryResult.commandType === "get_system_info" && (
            <>
              <p className="mb-1">
                {queryResult.data.hostname as string}
                <span className="text-muted"> — {queryResult.data.os as string}</span>
              </p>
              {queryResult.data.cpu_model ? (
                <p className="text-muted mb-1">{queryResult.data.cpu_model as string}</p>
              ) : null}
              {Array.isArray(queryResult.data.gpu) && (queryResult.data.gpu as string[]).length > 0 && (
                <p className="text-muted mb-1">{(queryResult.data.gpu as string[]).join(", ")}</p>
              )}
              {queryResult.data.gpu_lookup_error ? (
                <p className="text-danger text-xs mb-1">
                  GPU lookup failed: {queryResult.data.gpu_lookup_error as string}
                </p>
              ) : null}
              {queryResult.data.cpu_lookup_error ? (
                <p className="text-danger text-xs mb-1">
                  CPU name lookup failed (showing fallback): {queryResult.data.cpu_lookup_error as string}
                </p>
              ) : null}
              <p className="text-muted mb-2">
                {(queryResult.data.cpu_cores as number) ?? "?"} cores /{" "}
                {(queryResult.data.cpu_threads as number) ?? "?"} threads ·{" "}
                {(queryResult.data.ram_total_gb as number) ?? "?"} GB RAM · uptime{" "}
                {Math.floor(((queryResult.data.uptime_seconds as number) ?? 0) / 3600)}h
              </p>
              <table className="w-full text-xs" style={{ tableLayout: "fixed" }}>
                <thead>
                  <tr className="text-muted">
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "30%" }}>Drive</th>
                    <th className="text-left font-normal py-1" style={{ width: "70%" }}>Used</th>
                  </tr>
                </thead>
                <tbody>
                  {(queryResult.data.drives as Array<Record<string, unknown>> | undefined)?.map((d) => (
                    <tr key={d.drive as string} className="border-t border-line">
                      <td className="py-1 pr-2 mono">{d.drive as string}</td>
                      <td className="py-1">
                        {d.used_gb as number} / {d.total_gb as number} GB ({d.percent as number}%)
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {queryResult.commandType === "send_message" && (
            <p>
              {queryResult.data.ok ? (
                <span className="text-online">Message delivered — the dialog is showing on their screen now.</span>
              ) : (
                <span className="text-danger">Failed: {(queryResult.data.error as string) ?? "unknown error"}</span>
              )}
            </p>
          )}
          {queryResult.commandType === "kill_process" && (
            <p>
              {queryResult.data.ok ? (
                <span className="text-online">
                  Terminated {(queryResult.data.name as string) ?? "process"} (PID {queryResult.data.pid as number})
                </span>
              ) : (
                <span className="text-danger">Failed: {(queryResult.data.error as string) ?? "unknown error"}</span>
              )}
            </p>
          )}
          <button className="text-xs text-muted hover:text-text mt-2" onClick={() => setQueryResult(null)}>
            Close
          </button>
        </div>
      )}

      {/* Modal กรอก URL / Path แทน window.prompt เดิม */}
      {payloadModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setPayloadModal(null)}
        >
          <div
            className="bg-base border border-line rounded-xl p-5 w-full max-w-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-sm font-medium mb-3">{payloadModal.label}</h3>

            <input
              autoFocus
              type={payloadModal.kind === "pid" ? "number" : "text"}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitPayloadModal()}
              placeholder={
                payloadModal.kind === "url"
                  ? "https://example.com"
                  : payloadModal.kind === "path"
                  ? "C:\\Path\\To\\App.exe"
                  : payloadModal.kind === "pid"
                  ? "1234"
                  : "Save your work, restarting in 10 minutes"
              }
              className="w-full text-sm px-3 py-2 rounded-lg border border-line bg-transparent outline-none focus:border-accent"
            />

            {payloadModal.kind !== "pid" && loadRecents(payloadModal.kind).length > 0 && (
              <div className="mt-3">
                <p className="text-xs text-muted mb-1.5">Recent:</p>
                <div className="flex flex-wrap gap-1.5">
                  {loadRecents(payloadModal.kind).map((value) => (
                    <button
                      key={value}
                      onClick={() => setInputValue(value)}
                      className="text-xs px-2 py-1 rounded-md border border-line hover:border-accent transition truncate max-w-[180px]"
                      title={value}
                    >
                      {value}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setPayloadModal(null)}
                className="text-sm px-3 py-1.5 rounded-lg border border-line hover:bg-black/5 transition"
              >
                Cancel
              </button>
              <button
                onClick={submitPayloadModal}
                disabled={!inputValue.trim()}
                className="text-sm px-3 py-1.5 rounded-lg bg-accent text-white disabled:opacity-40 transition"
              >
                {payloadModal.needsConfirm ? "Next" : "Run"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal ยืนยันก่อน Restart / Shutdown / Lock / Sleep */}
      {confirmModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setConfirmModal(null)}
        >
          <div
            className="bg-base border border-line rounded-xl p-5 w-full max-w-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-sm font-medium mb-2">ยืนยันการทำรายการ</h3>
            <p className="text-sm text-muted">
              ต้องการ{CONFIRM_COPY[confirmModal.type]?.verb ?? confirmModal.label}{" "}
              {CONFIRM_COPY[confirmModal.type]?.subject?.(confirmModal.payload) ?? ""}
              เครื่องนี้จริงหรือไม่?
              {CONFIRM_COPY[confirmModal.type]?.hasGracePeriod && (
                <>
                  {" "}เครื่องปลายทางจะได้รับการแจ้งเตือนล่วงหน้า {SHUTDOWN_GRACE_SECONDS}{" "}
                  วินาทีก่อนทำจริง และสามารถกดยกเลิกได้ในช่วงนั้น
                </>
              )}
            </p>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setConfirmModal(null)}
                className="text-sm px-3 py-1.5 rounded-lg border border-line hover:bg-black/5 transition"
              >
                ยกเลิก
              </button>
              <button
                onClick={confirmDangerousAction}
                className="text-sm px-3 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 transition"
              >
                ยืนยัน{CONFIRM_COPY[confirmModal.type]?.verb ?? confirmModal.label}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
