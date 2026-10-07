import { Fragment, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  clearChatHistory,
  formatPrice,
  getChatHistory,
  sendChat,
  type ChatTurn,
  type PageContext,
  type ProductCard,
} from "../api.ts";
import { useAuth } from "../auth.tsx";
import { useChatResults } from "../chatResults.tsx";
import { Crest, displayName } from "../ui.tsx";

interface Message extends ChatTurn {
  products?: ProductCard[];
  error?: boolean;
  pageNote?: string; // "Showing 27 hoodies on the Products page"
  suggestions?: string[]; // quick replies from the agent (Problem 9)
}

/** Open the chat from anywhere: window.dispatchEvent(new CustomEvent(OPEN_CHAT_EVENT, { detail: { text } })). */
export const OPEN_CHAT_EVENT = "cc:open-chat";

/** Starter chips before the first question, based on the page (mirrors agent.default_suggestions). */
function starterChips(onProduct: boolean, hasResults: boolean): string[] {
  if (onProduct) return ["What sizes are in stock?", "What colors does it come in?", "Show me similar items"];
  if (hasResults) return ["Which is the cheapest?", "Only show ones in size M", "Any in gray?"];
  return ["What hoodies do you have?", "Show me crewnecks under $60", "Anything with a bulldog?"];
}

const greeting = (name?: string | null, returning = false): Message => ({
  role: "assistant",
  content: returning
    ? `Welcome back${name ? `, ${name}` : ""}! Your earlier chat is below, so pick up where you left off.`
    : `Good to see you${name ? `, ${name}` : ""}. I'm the Campus Customs concierge: ask me about any piece, size, color or what's on the rack today.`,
});

/** Render **bold** inside a line, without using innerHTML. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>,
  );
}

/** Minimal, safe markdown: paragraphs, "- " bullet lists and **bold**. */
function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      blocks.push(<ul key={`ul${blocks.length}`}>{list.map((l, i) => <li key={i}>{inline(l)}</li>)}</ul>);
      list = [];
    }
  };
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^[-*•]\s+(.*)$/) ?? line.match(/^\d+[.)]\s+(.*)$/);
    if (bullet) list.push(bullet[1]);
    else {
      flush();
      if (line) blocks.push(<p key={`p${blocks.length}`}>{inline(line)}</p>);
    }
  }
  flush();
  return <>{blocks}</>;
}

export default function ChatWidget() {
  const { user, loading: authLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { results, showResults } = useChatResults();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([greeting()]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Page context sent with every message (Problem 8): on /products/:id the agent knows which
  // item "this" is; on /products it knows which chat results are showing.
  const currentProductId = location.pathname.match(/^\/products\/([^/]+)$/)?.[1] ?? null;
  const page: PageContext = {
    path: location.pathname,
    product_id: currentProductId ? decodeURIComponent(currentProductId) : null,
    results_heading: location.pathname === "/products" && results ? results.heading : null,
  };

  // When the login state changes, restore that user's saved chat (or reset for guests).
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setMessages([greeting()]);
      return;
    }
    // Customer memory: reload this shopper's saved conversation from the database.
    getChatHistory()
      .then(({ messages: saved }) =>
        setMessages([
          greeting(user.first_name, saved.length > 0),
          ...saved.map((m) => ({ role: m.role, content: m.content, products: m.products })),
        ]),
      )
      .catch(() => setMessages([greeting(user.first_name)]));
  }, [user, authLoading]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open, sending]);

  const inputRef = useRef<HTMLInputElement>(null);

  // Other pages (e.g. the product page's "Ask about this product" button) can open the chat.
  useEffect(() => {
    const onOpen = (e: Event) => {
      setOpen(true);
      const text = (e as CustomEvent<{ text?: string }>).detail?.text;
      if (text) setInput(text);
      setTimeout(() => inputRef.current?.focus(), 50);
    };
    window.addEventListener(OPEN_CHAT_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_CHAT_EVENT, onOpen);
  }, []);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  async function send(raw: string) {
    const text = raw.trim();
    if (!text || sending) return;
    // Guests: send recent turns from the browser (skip the greeting and error bubbles).
    const history: ChatTurn[] = messages
      .slice(1)
      .filter((m) => !m.error)
      .map(({ role, content }) => ({ role, content }));
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setSending(true);
    try {
      const res = await sendChat(text, page, user ? [] : history);
      let pageNote: string | undefined;
      if (res.page_results && res.page_results.products.length > 0) {
        // API contract (Problem 7): structured matches -> render them on the Products page.
        showResults(res.page_results);
        if (location.pathname !== "/products") navigate("/products");
        pageNote = `Showing ${res.page_results.total_matches} result${res.page_results.total_matches === 1 ? "" : "s"} on the Products page`;
      }
      setMessages((m) => [
        ...m,
        { role: "assistant", content: res.reply, products: res.products, pageNote, suggestions: res.suggestions },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Sorry, I can't reach the server right now.";
      setMessages((m) => [...m, { role: "assistant", content: msg, error: true }]);
    } finally {
      setSending(false);
    }
  }

  async function handleClear() {
    if (!user || !window.confirm("Delete your saved chat history?")) return;
    try {
      await clearChatHistory();
      setMessages([greeting(user.first_name)]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Couldn't clear the history right now.", error: true }]);
    }
  }

  return (
    <div className="chat-root">
      {open && (
        <div className="chat-panel" role="dialog" aria-label="Campus Customs chat">
          <div className="chat-header">
            <span className="chat-title">
              <Crest size={26} className="crest-ivory" />
              <span>
                <span className="chat-name">The Concierge</span>
                <span className="chat-status"><span className="online-dot" aria-hidden="true" />Online · checks live stock</span>
              </span>
            </span>
            <span className="chat-header-actions">
              {user && messages.length > 1 && (
                <button type="button" className="chat-clear" onClick={handleClear} title="Delete saved chat history">
                  Clear
                </button>
              )}
              <button type="button" className="chat-close" onClick={() => setOpen(false)} aria-label="Close chat">
                ×
              </button>
            </span>
          </div>
          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={i} className={`chat-turn ${m.role}`}>
                <div className={`chat-msg ${m.role}${m.error ? " error" : ""}`}>
                  {m.role === "assistant" ? <RichText text={m.content} /> : m.content}
                </div>
                {m.pageNote && <div className="chat-page-note">↖ {m.pageNote}</div>}
                {m.products && m.products.length > 0 && (
                  <div className="chat-cards">
                    {m.products.map((p) => (
                      <Link key={p.product_id} to={`/products/${p.product_id}`} className="chat-card">
                        <img src={p.image_url} alt={p.name} loading="lazy" />
                        <span className="chat-card-name">{displayName(p.name)}</span>
                        <span className="chat-card-price">{formatPrice(p.price)}</span>
                      </Link>
                    ))}
                  </div>
                )}
                {i === messages.length - 1 && !sending && m.role === "assistant" && (
                  <div className="chat-chips" role="group" aria-label="Suggested questions">
                    {(m.suggestions?.length ? m.suggestions : starterChips(Boolean(currentProductId), Boolean(results)))
                      .map((sug) => (
                        <button type="button" key={sug} className="chat-chip" onClick={() => void send(sug)}>
                          {sug}
                        </button>
                      ))}
                  </div>
                )}
              </div>
            ))}
            {sending && (
              <div className="chat-msg assistant typing" aria-label="The concierge is typing">
                <span /><span /><span />
              </div>
            )}
            <div ref={endRef} />
          </div>
          <div className="chat-context">
            {user ? `Chatting as ${user.first_name ?? user.name} · history saved` : "Guest · log in to save this chat"}
            {currentProductId ? " · asking about this product" : ""}
          </div>
          <form className="chat-input" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={currentProductId ? "Ask about this piece…" : "Ask the concierge…"}
              aria-label="Message"
              maxLength={2000}
            />
            <button type="submit" className="chat-send" disabled={sending || !input.trim()} aria-label="Send">
              ↑
            </button>
          </form>
        </div>
      )}
      <button
        type="button"
        className={`chat-toggle${open ? " is-open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close chat" : "Open chat"}
      >
        {open ? (
          <span className="chat-toggle-x">×</span>
        ) : (
          <>
            <Crest size={22} className="crest-ivory" />
            <span className="chat-toggle-label">Ask the Concierge</span>
          </>
        )}
      </button>
    </div>
  );
}
