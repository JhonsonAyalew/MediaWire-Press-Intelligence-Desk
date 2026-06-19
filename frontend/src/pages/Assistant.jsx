import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import PageHeader from "../components/PageHeader.jsx";
import "./Assistant.css";

const SESSION_ID = "desk-session";

const SUGGESTIONS = [
  "How many journalists do I have with an email on file?",
  "Which outlet am I weakest in for AI/tech coverage?",
  "Summarize who I have covering climate or energy.",
];

export default function Assistant() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "I'm the desk assistant — ask me about your scraped database, who's worth pitching, or what's missing from your coverage list." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || loading) return;
    setMessages((m) => [...m, { role: "user", content: message }]);
    setInput("");
    setLoading(true);
    setError("");
    try {
      const { data } = await api.chat({ session_id: SESSION_ID, message });
      setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="assistant-page">
      <PageHeader
        eyebrow="AI Assistant"
        title="Ask the Desk"
        description="Backed by the Anthropic API and a live snapshot of your database — ask about coverage gaps, specific journalists, or what to pitch next."
      />

      <div className="chat-window">
        <div className="chat-window__messages">
          {messages.map((m, i) => (
            <div key={i} className={`bubble bubble--${m.role}`}>
              {m.content}
            </div>
          ))}
          {loading && <div className="bubble bubble--assistant bubble--loading">thinking…</div>}
          <div ref={bottomRef} />
        </div>

        {error && <p className="modal__error" style={{ padding: "0 18px" }}>{error}</p>}

        <div className="chat-suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} className="chip" onClick={() => send(s)}>{s}</button>
          ))}
        </div>

        <div className="chat-input">
          <input
            placeholder="Ask about your journalist database…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button className="btn-primary" onClick={() => send()} disabled={loading}>Send</button>
        </div>
      </div>
    </div>
  );
}
