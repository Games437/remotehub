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
  { type: "lock", label: "Lock" },
  { type: "sleep", label: "Sleep" },
  { type: "restart", label: "Restart", needsConfirm: true },
  { type: "shutdown", label: "Shutdown", needsConfirm: true },
];

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

  // -- state ใหม่สำหรับ modal / recent values --
  const [payloadModal, setPayloadModal] = useState<PayloadModalState | null>(null);
  const [confirmModal, setConfirmModal] = useState<ConfirmModalState | null>(null);
  const [inputValue, setInputValue] = useState("");

  const { data: activeCommand } = useCommand(machineId, activeCommandId);

  useEffect(() => {
    if (!activeCommand) return;

    if (
      activeCommand.status !== "acknowledged" &&
      activeCommand.status !== "failed"
    ) {
      return;
    }

    // 🌟 1. แก้ไขจาก image_base64 เป็น image_b64 ให้ตรงกับฐานข้อมูล
    if (
      activeCommand.command_type === "screenshot" &&
      activeCommand.status === "acknowledged" &&
      activeCommand.result?.image_b64
    ) {
      try {
        const format = activeCommand.result.format ?? "png";

        // 🌟 2. ดึงค่าจากคีย์ image_b64
        const base64Data = activeCommand.result.image_b64;

        // 🌟 3. ปรับปรุงการแปลง Base64 เป็น Blob ให้เสถียรและสั้นลงผ่าน fetch Data URL
        fetch(`data:image/${format};base64,${base64Data}`)
          .then((res) => res.blob())
          .then((blob) => {
            const url = URL.createObjectURL(blob);

            const link = document.createElement("a");
            link.href = url;
            link.download = `screenshot-${machineId}-${Date.now()}.${format}`;

            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            URL.revokeObjectURL(url);

            // 4. ล้างผลลัพธ์ออกจากเซิร์ฟเวอร์หลังดาวน์โหลดเสร็จตามโค้ดเดิมของคุณ
            purgeResult.mutate(activeCommand.id, {
              onError: (err) => {
                console.error("Failed to purge screenshot:", err);
              },
            });
          })
          .catch((err) => console.error("Blob generation failed:", err));
      } catch (err) {
        console.error("Failed to download screenshot:", err);
      }
    }

    setActiveCommandId(null);
    setPendingType(null);
  }, [activeCommand, machineId, purgeResult]);

  // ฟังก์ชันยิงคำสั่งจริง (เดิมชื่อ run แยกออกมาเป็น dispatch เพื่อให้
  // ทั้ง modal กรอกข้อมูล และ modal ยืนยัน เรียกใช้ร่วมกันได้)
  function dispatch(type: string, payload?: Record<string, unknown>) {
    setPendingType(type);

    sendCommand.mutate(
      {
        command_type: type,
        payload,
      },
      {
        onSuccess: (data) => {
          setActiveCommandId(data.id);
        },
        onError: () => {
          setPendingType(null);
        },
      },
    );
  }

  // จุดตัดสินใจตอนกดปุ่ม: ต้องกรอกข้อมูลก่อนไหม / ต้องยืนยันก่อนไหม / ยิงเลย
  function handleActionClick(action: (typeof ACTIONS)[number]) {
    if (action.needsPayload) {
      setInputValue("");
      setPayloadModal({
        type: action.type,
        label: action.label,
        kind: action.needsPayload,
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
    saveRecent(payloadModal.kind, inputValue.trim());
    dispatch(payloadModal.type, { [payloadModal.kind]: inputValue.trim() });
    setPayloadModal(null);
  }

  function confirmDangerousAction() {
    if (!confirmModal) return;
    dispatch(confirmModal.type);
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
      </div>

      {activeCommand?.status === "failed" && (
        <p className="text-sm text-red-500 mt-2">
          Command failed
          {activeCommand.result?.error
            ? `: ${String(activeCommand.result.error)}`
            : ""}
        </p>
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
                payloadModal.kind === "url"
                  ? "https://example.com"
                  : "C:\\Path\\To\\App.exe"
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
              เครื่องนี้จริงหรือไม่? โปรแกรมที่เปิดอยู่บนเครื่องปลายทางอาจถูกปิด
              โดยไม่ได้บันทึกงานไว้
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