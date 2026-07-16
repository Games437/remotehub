import { useEffect, useRef, useState } from "react";
import { Machine, useDeleteMachine, formatDuration } from "../hooks/useMachines";
import CommandButtons from "./CommandButtons";

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex-1">
      <div className="flex justify-between text-xs text-muted mb-1">
        <span>{label}</span>
        <span className="mono">{value != null ? `${Math.round(value)}%` : "—"}</span>
      </div>
      <div className="h-1.5 rounded-full bg-line overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all"
          style={{ width: `${value ?? 0}%` }}
        />
      </div>
    </div>
  );
}

export default function MachineCard({ machine }: { machine: Machine }) {
  const deleteMachine = useDeleteMachine();
  const online = machine.status === "online";

  // Proactive idle alert: fires once per 30-minute milestone (30 min,
  // 1h, 1h30, ...) instead of requiring someone to click "Idle time" to
  // notice nobody's at the keyboard. Resets the moment activity brings
  // idle_seconds back down (i.e. someone's back).
  const [idleAlert, setIdleAlert] = useState<string | null>(null);
  const lastAlertedThreshold = useRef(0);
  const prevIdleSeconds = useRef<number | null>(null);

  useEffect(() => {
    const idle = machine.idle_seconds;
    if (idle == null) {
      lastAlertedThreshold.current = 0;
      prevIdleSeconds.current = null;
      setIdleAlert(null);
      return;
    }
    if (prevIdleSeconds.current != null && idle < prevIdleSeconds.current) {
      // idle time went down — activity happened, someone's back
      lastAlertedThreshold.current = 0;
      setIdleAlert(null);
    }
    prevIdleSeconds.current = idle;

    const THIRTY_MIN_SECONDS = 30 * 60;
    const currentThreshold = Math.floor(idle / THIRTY_MIN_SECONDS);
    if (currentThreshold >= 1 && currentThreshold > lastAlertedThreshold.current) {
      lastAlertedThreshold.current = currentThreshold;
      const totalMinutes = currentThreshold * 30;
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;
      const thaiDuration =
        hours > 0
          ? minutes > 0
            ? `${hours} ชั่วโมง ${minutes} นาที`
            : `${hours} ชั่วโมง`
          : `${minutes} นาที`;
      setIdleAlert(`ไม่อยู่หน้าจอมา ${thaiDuration}แล้ว`);
    }
  }, [machine.idle_seconds]);

  return (
    <div className="bg-panel border border-line rounded-xl p-5">
      {idleAlert && (
        <div className="mb-3 text-sm bg-base border border-line rounded-lg px-3 py-2 flex items-center justify-between">
          <span>{idleAlert}</span>
          <button
            className="text-xs text-muted hover:text-text ml-3"
            onClick={() => setIdleAlert(null)}
          >
            Dismiss
          </button>
        </div>
      )}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: online ? "#3DDC97" : "#5A6376" }}
            />
            <h3 className="font-medium">{machine.name}</h3>
          </div>
          <p className="text-xs text-muted mono mt-1">{machine.machine_uid}</p>
        </div>
        <button
          className="text-xs text-muted hover:text-danger transition"
          onClick={() => {
            if (window.confirm(`Remove "${machine.name}"? This cannot be undone.`)) {
              deleteMachine.mutate(machine.id);
            }
          }}
        >
          Remove
        </button>
      </div>

      <div className="flex gap-4 mb-4">
        <Stat label="CPU" value={machine.cpu_percent} />
        <Stat label="RAM" value={machine.ram_percent} />
        <Stat label="Disk" value={machine.disk_percent} />
      </div>

      <div className="flex justify-between text-xs text-muted mb-4">
        <span>
          {machine.os ?? "Unknown OS"}
          {online && machine.idle_seconds != null && machine.idle_seconds >= 60 && (
            <span> · idle {formatDuration(machine.idle_seconds)}</span>
          )}
        </span>
        <span className="mono">{machine.ip_address ?? "—"}</span>
      </div>

      <CommandButtons machineId={machine.id} online={online} />
    </div>
  );
}
