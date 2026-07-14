import { Link } from "react-router-dom";
import { useAuditLogs } from "../hooks/useMachines";

const ACTION_LABELS: Record<string, string> = {
  login: "Signed in",
  login_2fa: "2FA check",
  register: "Account created",
  password_reset: "Password reset",
  machine_paired: "Machine paired",
  machine_deleted: "Machine removed",
  access_granted: "Access role changed",
  command_sent: "Command sent",
  command_result_purged: "Screenshot data cleared",
  "2fa_enabled": "2FA enabled",
  "2fa_disabled": "2FA disabled",
};

export default function ActivityLog() {
  const { data: logs, isLoading } = useAuditLogs();

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Activity log</h1>
          <p className="text-muted text-sm">
            Every action taken on your account and machines — the record of what
            happened, since there's no live screen to watch in real time.
          </p>
        </div>
        <Link to="/" className="text-sm text-accent">
          Back to dashboard
        </Link>
      </div>

      {isLoading && <p className="text-muted text-sm">Loading...</p>}

      {!isLoading && logs?.length === 0 && (
        <p className="text-muted text-sm">No activity recorded yet.</p>
      )}

      <div className="space-y-2">
        {logs?.map((entry) => (
          <div
            key={entry.id}
            className="bg-panel border border-line rounded-lg px-4 py-3 flex items-start justify-between text-sm"
          >
            <div>
              <p>
                <span
                  className={entry.result === "failure" ? "text-danger" : "text-text"}
                >
                  {ACTION_LABELS[entry.action] ?? entry.action}
                </span>
                {entry.detail?.command_type ? (
                  <span className="text-muted mono"> · {String(entry.detail.command_type)}</span>
                ) : null}
              </p>
              {entry.ip_address && (
                <p className="text-xs text-muted mono mt-0.5">{entry.ip_address}</p>
              )}
            </div>
            <span className="text-xs text-muted whitespace-nowrap ml-4">
              {new Date(entry.created_at).toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
