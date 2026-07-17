import { useState } from "react";
import { useChatHistory, useSendChat } from "../hooks/useMachines";

export default function ChatPanel({ machineId }: { machineId: string }) {
  const [message, setMessage] = useState("");
  const chat = useChatHistory(machineId, true);
  const sendChat = useSendChat(machineId);

  function submit() {
    if (!message.trim()) return;
    sendChat.mutate(message.trim());
    setMessage("");
  }

  return (
    <div className="mt-2 bg-base border border-line rounded-lg p-3">
      <div className="flex flex-col gap-2 mb-2 max-h-56 overflow-auto">
        {chat.isLoading && <p className="text-muted text-xs">Loading...</p>}
        {chat.data?.length === 0 && (
          <p className="text-muted text-xs">No messages yet — say something.</p>
        )}
        {chat.data?.map((m) => (
          <div
            key={m.id}
            className={`text-sm px-3 py-1.5 rounded-lg max-w-[80%] ${
              m.sender === "admin"
                ? "self-end bg-accent text-white rounded-br-sm"
                : "self-start bg-panel rounded-bl-sm"
            }`}
          >
            {m.message}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Message this machine"
          className="flex-1 text-sm px-3 py-2 rounded-lg border border-line bg-transparent outline-none focus:border-accent"
        />
        <button
          disabled={!message.trim() || sendChat.isPending}
          onClick={submit}
          className="px-3 py-1.5 rounded-lg border border-line hover:border-accent disabled:opacity-40 transition"
        >
          Send
        </button>
      </div>
    </div>
  );
}
