import { useState } from "react";
import { api } from "../api.js";
import "./DraftModal.css";

export default function DraftModal({ author, onClose }) {
  const [context, setContext] = useState("");
  const [senderName, setSenderName] = useState("");
  const [senderOrg, setSenderOrg] = useState("");
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  async function generate() {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.draftEmail({
        author_id: author.id,
        campaign_context: context,
        sender_name: senderName,
        sender_org: senderOrg,
      });
      setDraft(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function copyAll() {
    if (!draft) return;
    navigator.clipboard.writeText(`Subject: ${draft.subject}\n\n${draft.body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <div>
            <p className="eyebrow">Draft Outreach — {author.outlet}</p>
            <h2 className="modal__title">{author.name}</h2>
          </div>
          <button className="btn-ghost" onClick={onClose}>Close</button>
        </div>

        <div className="modal__body">
          <label className="field">
            <span className="eyebrow">Pitch / campaign context</span>
            <textarea
              rows={3}
              placeholder="e.g. We're launching an open-source benchmark for small-model inference costs — relevant to their AI infra coverage."
              value={context}
              onChange={(e) => setContext(e.target.value)}
            />
          </label>

          <div className="field-row">
            <label className="field">
              <span className="eyebrow">Your name</span>
              <input value={senderName} onChange={(e) => setSenderName(e.target.value)} placeholder="Jane Doe" />
            </label>
            <label className="field">
              <span className="eyebrow">Your org</span>
              <input value={senderOrg} onChange={(e) => setSenderOrg(e.target.value)} placeholder="Acme PR" />
            </label>
          </div>

          <button className="btn-primary" onClick={generate} disabled={loading}>
            {loading ? "Drafting…" : "Draft with AI"}
          </button>

          {error && <p className="modal__error">{error}</p>}

          {draft && (
            <div className="draft-output">
              <p className="eyebrow">Subject</p>
              <p className="draft-output__subject">{draft.subject}</p>
              <p className="eyebrow" style={{ marginTop: 14 }}>Body</p>
              <p className="draft-output__body">{draft.body}</p>
              <button className="btn-ghost" onClick={copyAll}>{copied ? "Copied" : "Copy to clipboard"}</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
