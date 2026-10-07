import { createContext, useContext, useState, type ReactNode } from "react";
import type { PageResults } from "./api.ts";

/**
 * Shared state for Problem 7: the chat widget puts the agent's structured product matches
 * here, and the Products page renders them instead of the full catalogue.
 */
interface ChatResultsState {
  results: (PageResults & { receivedAt: number }) | null;
  showResults: (r: PageResults) => void;
  clearResults: () => void;
}

const ChatResultsContext = createContext<ChatResultsState | null>(null);

export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<ChatResultsState["results"]>(null);
  const value: ChatResultsState = {
    results,
    showResults: (r) => setResults({ ...r, receivedAt: Date.now() }),
    clearResults: () => setResults(null),
  };
  return <ChatResultsContext.Provider value={value}>{children}</ChatResultsContext.Provider>;
}

export function useChatResults(): ChatResultsState {
  const ctx = useContext(ChatResultsContext);
  if (!ctx) throw new Error("useChatResults must be used inside <ChatResultsProvider>");
  return ctx;
}
