import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

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