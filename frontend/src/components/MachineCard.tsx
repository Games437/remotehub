import { Machine, useDeleteMachine } from "../hooks/useMachines";
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

  return (
    <div className="bg-panel border border-line rounded-xl p-5">
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
        <span>{machine.os ?? "Unknown OS"}</span>
        <span className="mono">{machine.ip_address ?? "—"}</span>
      </div>

      <CommandButtons machineId={machine.id} online={online} />
    </div>
  );
}
