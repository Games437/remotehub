import { useEffect, useState } from "react";
import {
  useSendCommand,
  useCommand,
  usePurgeCommandResult,
} from "../hooks/useMachines";

const ACTIONS: {
  type: string;
  label: string;
  needsPayload?: "url" | "path";
  needsConfirm?: boolean;
}[] = [
  { type: "open_website", label: "Open website", needsPayload: "url" },
  { type: "open_program", label: "Open program", needsPayload: "path" },
  { type: "screenshot", label: "Screenshot" },
  { type: "get_idle_time", label: "Idle time" },
  { type: "list_processes", label: "Processes" },
  { type: "get_active_window", label: "Active window" },
  { type: "list_open_windows", label: "Open windows" },
  { type: "get_network_status", label: "Network status" },
  { type: "lock", label: "Lock" },
  { type: "sleep", label: "Sleep" },
  { type: "restart", label: "Restart", needsConfirm: true },
  { type: "shutdown", label: "Shutdown", needsConfirm: true },
];

const SHUTDOWN_GRACE_SECONDS = 60;
const RECENTS_KEY_PREFIX = "remotehub:recents:";
const MAX_RECENTS = 5;

function loadRecents(kind: "url" | "path"): string[] {
  try {
    const raw = localStorage.getItem(RECENTS_KEY_PREFIX + kind);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function saveRecent(kind: "url" | "path", value: string) {
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
  kind: "url" | "path";
}

interface ConfirmModalState {
  type: string;
  label: string;
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
      } else if (
        type === "get_idle_time" ||
        type === "list_processes" ||
        type === "get_active_window" ||
        type === "list_open_windows" ||
        type === "get_network_status"
      ) {
        setQueryResult({ commandType: type, data: result || {} });
      } else if (type === "shutdown" || type === "restart") {
        setShutdownPending(type);
      } else if (type === "cancel_shutdown") {
        setShutdownPending(null);
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
    if (action.needsPayload) {
      setInputValue("");
      setPayloadModal({ type: action.type, label: action.label, kind: action.needsPayload });
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
    saveRecent(payloadModal.kind, inputValue.trim());
    dispatch(payloadModal.type, { [payloadModal.kind]: inputValue.trim() });
    setPayloadModal(null);
  }

  function confirmDangerousAction() {
    if (!confirmModal) return;
    // Shutdown/restart always go out with a grace period + local notification
    // — the agent warns whoever's at the keyboard and gives them time to
    // cancel, since the operator sending this has no live view of the screen.
    dispatch(confirmModal.type, { delay_seconds: SHUTDOWN_GRACE_SECONDS });
    setConfirmModal(null);
  }

  const isBusy = (type: string) =>
    pendingType === type &&
    (sendCommand.isPending ||
      (activeCommand?.status !== "acknowledged" &&
        activeCommand?.status !== "failed"));

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((action) => (
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
              : `Cancel ${shutdownPending} (${SHUTDOWN_GRACE_SECONDS}s grace period)`}
          </button>
        )}
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
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "55%" }}>Program</th>
                    <th className="text-left font-normal py-1 pr-2" style={{ width: "22%" }}>Memory</th>
                    <th className="text-left font-normal py-1" style={{ width: "23%" }}>CPU</th>
                  </tr>
                </thead>
                <tbody>
                  {(queryResult.data.processes as Array<Record<string, unknown>> | undefined)?.map((p) => (
                    <tr key={p.name as string} className="border-t border-line">
                      <td className="py-1 pr-2 truncate" title={p.name as string}>
                        {p.name as string}
                        {(p.instance_count as number) > 1 ? (
                          <span className="text-muted"> (×{p.instance_count as number})</span>
                        ) : null}
                      </td>
                      <td className="py-1 pr-2 mono">{(p.memory_percent as number).toFixed(1)}%</td>
                      <td className="py-1 mono">{(p.cpu_percent as number).toFixed(1)}%</td>
                    </tr>
                  ))}
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
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitPayloadModal()}
              placeholder={
                payloadModal.kind === "url" ? "https://example.com" : "C:\\Path\\To\\App.exe"
              }
              className="w-full text-sm px-3 py-2 rounded-lg border border-line bg-transparent outline-none focus:border-accent"
            />

            {loadRecents(payloadModal.kind).length > 0 && (
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
                Run
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal ยืนยันก่อน Restart / Shutdown */}
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
              ต้องการ{confirmModal.label === "Restart" ? "รีสตาร์ท" : "ปิดเครื่อง"}
              เครื่องนี้จริงหรือไม่? เครื่องปลายทางจะได้รับการแจ้งเตือนล่วงหน้า{" "}
              {SHUTDOWN_GRACE_SECONDS} วินาทีก่อนทำจริง และสามารถกดยกเลิกได้ในช่วงนั้น
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
                ยืนยัน{confirmModal.label === "Restart" ? "รีสตาร์ท" : "ปิดเครื่อง"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
