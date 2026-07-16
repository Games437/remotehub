import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

// Minutes/hours instead of raw seconds — "1h 30m" reads at a glance,
// "5412 seconds" doesn't.
export function formatDuration(totalSeconds: number): string {
  if (totalSeconds < 60) return "< 1 min";
  const totalMinutes = Math.floor(totalSeconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes} min`;
  if (minutes === 0) return `${hours}h`;
  return `${hours}h ${minutes}m`;
}

export interface Machine {
  id: string;
  name: string;
  machine_uid: string;
  status: "online" | "offline";
  last_seen: string | null;
  os: string | null;
  cpu_percent: number | null;
  ram_percent: number | null;
  disk_percent: number | null;
  idle_seconds: number | null;
  ip_address: string | null;
}

export function useMachines() {
  return useQuery({
    queryKey: ["machines"],
    queryFn: async () => {
      const { data } = await api.get<Machine[]>("/machines");
      return data;
    },
    refetchInterval: 10_000, // simple polling; swap for a shared websocket subscription later
  });
}

export function useGeneratePairCode() {
  return useMutation({
    mutationFn: async (machine_name: string) => {
      const { data } = await api.post("/machines/pair/generate-code", { machine_name });
      return data as { code: string; expires_in_seconds: number };
    },
  });
}

export function useSendCommand(machineId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { command_type: string; payload?: Record<string, unknown> }) => {
      const { data } = await api.post(`/machines/${machineId}/commands`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["machines"] }),
  });
}

export function useDeleteMachine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (machineId: string) => {
      await api.delete(`/machines/${machineId}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["machines"] }),
  });
}

export interface Command {
  id: string;
  machine_id: string;
  command_type: string;
  status: "pending" | "sent" | "acknowledged" | "failed";
  result: Record<string, unknown> | null;
  created_at: string;
}

/**
 * Polls a single command until the agent acknowledges (or fails) it.
 * There's no GET /commands/{id} endpoint, so this re-fetches the list
 * and picks out the one we care about — fine at this table size (<=100).
 */
export function useCommand(machineId: string, commandId: string | null) {
  return useQuery({
    queryKey: ["commands", machineId, commandId],
    queryFn: async () => {
      const { data } = await api.get<Command[]>(`/machines/${machineId}/commands`);
      return data.find((c) => c.id === commandId) ?? null;
    },
    enabled: !!commandId,
    refetchInterval: (query) => {
      const cmd = query.state.data;
      if (!cmd) return 1500;
      return cmd.status === "acknowledged" || cmd.status === "failed" ? false : 1500;
    },
  });
}

export interface CommandHistoryPage {
  commands: Command[];
  total: number;
}

const HISTORY_PAGE_SIZE = 20;

/** Paginated command history for a machine — separate from useCommand
 * above, which only tracks the one command just sent. */
export function useCommandHistory(machineId: string, page: number, enabled: boolean) {
  return useQuery({
    queryKey: ["command-history", machineId, page],
    queryFn: async (): Promise<CommandHistoryPage> => {
      const { data, headers } = await api.get<Command[]>(`/machines/${machineId}/commands`, {
        params: { skip: page * HISTORY_PAGE_SIZE, limit: HISTORY_PAGE_SIZE },
      });
      const total = Number(headers["x-total-count"] ?? data.length);
      return { commands: data, total };
    },
    enabled,
    placeholderData: (previous) => previous, // keep old page visible while the next one loads
  });
}

export { HISTORY_PAGE_SIZE };

export function usePurgeCommandResult(machineId: string) {
  return useMutation({
    mutationFn: async (commandId: string) => {
      await api.delete(`/machines/${machineId}/commands/${commandId}/result`);
    },
  });
}

export interface AuditLogEntry {
  id: string;
  action: string;
  resource: string | null;
  ip_address: string | null;
  result: "success" | "failure";
  detail: Record<string, unknown> | null;
  created_at: string;
}

export function useAuditLogs() {
  return useQuery({
    queryKey: ["audit-logs"],
    queryFn: async () => {
      const { data } = await api.get<AuditLogEntry[]>("/audit-logs");
      return data;
    },
    refetchInterval: 15_000,
  });
}