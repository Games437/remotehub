import { useState } from "react";
import { Link } from "react-router-dom";
import { logout } from "../hooks/useAuth";
import { useGeneratePairCode, useMachines } from "../hooks/useMachines";
import MachineCard from "../components/MachineCard";

function AddMachineModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const generateCode = useGeneratePairCode();

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-10">
      <div className="bg-panel border border-line rounded-xl p-6 w-full max-w-sm">
        <h2 className="font-medium mb-4">Add a machine</h2>

        {!generateCode.data ? (
          <>
            <label className="block text-sm text-muted mb-1">Machine name</label>
            <input
              className="w-full mb-4 bg-base border border-line rounded-lg px-3 py-2 outline-none focus:border-accent"
              placeholder="e.g. Office PC"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <div className="flex gap-2">
              <button className="text-sm text-muted" onClick={onClose}>Cancel</button>
              <button
                className="ml-auto bg-accent rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40"
                disabled={!name || generateCode.isPending}
                onClick={() => generateCode.mutate(name)}
              >
                Generate pairing code
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm text-muted mb-2">
              Run the agent installer on the target machine and enter this code when prompted:
            </p>
            <p className="mono text-2xl text-center bg-base border border-line rounded-lg py-4 mb-4 tracking-widest">
              {generateCode.data.code}
            </p>
            <p className="text-xs text-muted mb-4">
              Expires in {Math.round(generateCode.data.expires_in_seconds / 60)} minutes. The machine will
              appear here automatically once it's paired.
            </p>
            <button className="w-full bg-accent rounded-lg py-2 text-sm font-medium" onClick={onClose}>
              Done
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: machines, isLoading } = useMachines();
  const [showAdd, setShowAdd] = useState(false);

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold">Your machines</h1>
          <p className="text-muted text-sm">
            {machines?.length ?? 0} machine{machines?.length === 1 ? "" : "s"} connected
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/help" className="text-sm text-muted hover:text-text transition">
            Help / Download
          </Link>
          <Link to="/activity" className="text-sm text-muted hover:text-text transition">
            Activity log
          </Link>
          <button
            className="bg-accent rounded-lg px-4 py-2 text-sm font-medium"
            onClick={() => setShowAdd(true)}
          >
            Add machine
          </button>
          <button className="text-sm text-muted hover:text-text transition" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>

      {isLoading && <p className="text-muted text-sm">Loading...</p>}

      {!isLoading && machines?.length === 0 && (
        <div className="border border-dashed border-line rounded-xl p-12 text-center">
          <p className="text-muted mb-4">No machines yet. Add one to get started.</p>
          <button className="bg-accent rounded-lg px-4 py-2 text-sm font-medium" onClick={() => setShowAdd(true)}>
            Add your first machine
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {machines?.map((m) => (
          <MachineCard key={m.id} machine={m} />
        ))}
      </div>

      {showAdd && <AddMachineModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}
