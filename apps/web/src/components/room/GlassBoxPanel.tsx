'use client';

/**
 * GlassBoxPanel — Pillar 1: the 60-second WOW.
 *
 * Split view. Left: every reviewer question, attributed to its persona, each
 * carrying a citation chip. Right: the exact source passage the claim was
 * grounded in — with the quoted line highlighted, the page, and a re-verified
 * sha256 badge. Ungrounded claims show a red "evidence gap": the reviewer is
 * probing something the materials don't actually support.
 */
import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { getProvenance, demoUngroundedCitation, ProvenanceResponse, ProvenanceClaim, UngroundedCitationDemo } from '@/lib/api';
import { keyStore } from '@/lib/openrouterKeyStore';
import styles from './GlassBoxPanel.module.css';

// pdfjs touches browser globals at import time — must never run during SSR.
const PdfSourceViewer = dynamic(() => import('./PdfSourceViewer'), { ssr: false });

interface Props {
  debateId: string;
}

/** Side-by-side: what a model claims as the source WITHOUT the manuscript vs
 *  PeerForge's verified line. The left answer is generated live — no staging. */
function TrustComparison({ debateId, claim }: { debateId: string; claim: ProvenanceClaim }) {
  const [demo, setDemo] = useState<UngroundedCitationDemo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset when the selected claim changes.
  useEffect(() => { setDemo(null); setError(null); }, [claim.claim_id]);

  const run = async () => {
    const key = keyStore.getKey();
    if (!key) { setError('Add your OpenRouter key in Settings to run the comparison.'); return; }
    setLoading(true);
    setError(null);
    try {
      setDemo(await demoUngroundedCitation(debateId, claim.text, key));
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.compareCard}>
      {!demo ? (
        <div className={styles.compareIntro}>
          <button className={styles.compareBtn} onClick={run} disabled={loading}>
            {loading ? 'Asking the trust-me AI…' : '⚖️ Compare: ask an AI with NO document for this source'}
          </button>
          {error && <span className={styles.compareError}>{error}</span>}
        </div>
      ) : (
        <div className={styles.compareGrid}>
          <div className={styles.compareSide}>
            <div className={styles.compareLabelBad}>Trust-me AI — given no manuscript</div>
            <p className={styles.compareAnswer}>“{demo.answer}”</p>
            <div className={styles.compareFoot}>
              {demo.model} · unverifiable — the model never saw your document
            </div>
          </div>
          <div className={styles.compareSide}>
            <div className={styles.compareLabelGood}>PeerForge — verified against your manuscript</div>
            <p className={styles.compareAnswer}>“{claim.excerpt}”</p>
            <div className={styles.compareFoot}>
              {claim.source?.doc_title}
              {claim.source?.page_num != null && ` · p.${claim.source.page_num}`}
              {claim.source?.sha256_verified && ' · 🔒 sha256 verified'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function HighlightedChunk({ claim }: { claim: ProvenanceClaim }) {
  const src = claim.source;
  if (!src) return null;
  const text = src.chunk_text || '';
  const hl = src.highlight;
  if (!hl || hl.start == null || hl.end == null || hl.start >= hl.end) {
    return <p className={styles.chunkText}>{text}</p>;
  }
  return (
    <p className={styles.chunkText}>
      {text.slice(0, hl.start)}
      <mark className={styles.mark}>{text.slice(hl.start, hl.end)}</mark>
      {text.slice(hl.end)}
    </p>
  );
}

export default function GlassBoxPanel({ debateId }: Props) {
  const [data, setData] = useState<ProvenanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pdfOpen, setPdfOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    getProvenance(debateId)
      .then((d) => {
        if (!alive) return;
        setData(d);
        const firstGrounded = d.claims.find((c) => c.grounded) || d.claims[0];
        setSelectedId(firstGrounded?.claim_id ?? null);
      })
      .catch((e) => alive && setError(String(e?.message || e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [debateId]);

  const selected = useMemo(
    () => data?.claims.find((c) => c.claim_id === selectedId) ?? null,
    [data, selectedId]
  );

  // Close the PDF modal when the user switches claims — otherwise it silently
  // swaps to the new claim's material while open.
  useEffect(() => { setPdfOpen(false); }, [selectedId]);

  if (loading) return <div className={styles.state}>Loading evidence map…</div>;
  if (error) return <div className={styles.state}>Could not load provenance: {error}</div>;
  if (!data || data.claims.length === 0) {
    return (
      <div className={styles.state}>
        No reviewer questions yet. Generate questions in <strong>Practice&nbsp;Q&amp;A</strong> to
        build the evidence map.
      </div>
    );
  }

  const { summary } = data;

  return (
    <div className={styles.wrap}>
      {/* Header: verified evidence scoreboard */}
      <header className={styles.header}>
        <div>
          <h3 className={styles.title}>Glass-Box Evidence Map</h3>
          <p className={styles.subtitle}>
            Every reviewer question is traced to the exact source line it stands on — or flagged
            where your materials don&apos;t back it up.
          </p>
        </div>
        <div className={styles.scoreboard}>
          <div className={styles.stat}>
            <span className={styles.statNum}>{summary.grounded}</span>
            <span className={styles.statLbl}>grounded</span>
          </div>
          <div className={`${styles.stat} ${styles.statGap}`}>
            <span className={styles.statNum}>{summary.gaps}</span>
            <span className={styles.statLbl}>evidence gaps</span>
          </div>
          <div className={`${styles.stat} ${styles.statVerified}`}>
            <span className={styles.statNum}>{summary.sha256_verified}</span>
            <span className={styles.statLbl}>sha256 verified</span>
          </div>
        </div>
      </header>

      <div className={styles.split}>
        {/* Left: reviewer claims */}
        <section className={styles.left}>
          {data.claims.map((c) => {
            const active = c.claim_id === selectedId;
            return (
              <button
                key={c.claim_id}
                className={`${styles.claim} ${active ? styles.claimActive : ''}`}
                onClick={() => setSelectedId(c.claim_id)}
              >
                <div className={styles.claimHead}>
                  <span className={styles.persona}>{c.persona}</span>
                  <span className={styles.category}>{c.category?.replace(/_/g, ' ')}</span>
                </div>
                <p className={styles.claimText}>{c.text}</p>
                {c.grounded && c.source ? (
                  <span className={`${styles.chip} ${styles.chipOk}`}>
                    ✓ GROUNDED
                    {c.source.sha256_verified && ' · sha256 verified'}
                    {c.source.page_num != null && ` · p.${c.source.page_num}`}
                  </span>
                ) : (
                  <span className={`${styles.chip} ${styles.chipGap}`}>⚠ EVIDENCE GAP</span>
                )}
              </button>
            );
          })}
        </section>

        {/* Right: the source */}
        <section className={styles.right}>
          {!selected ? (
            <div className={styles.state}>Select a question to see its source.</div>
          ) : selected.grounded && selected.source ? (
            <div className={styles.sourceCard}>
              <div className={styles.sourceHead}>
                <span className={styles.docTitle}>📄 {selected.source.doc_title}</span>
                <span className={styles.sourceHeadActions}>
                  {selected.source.page_num != null && (
                    <span className={styles.pageBadge}>page {selected.source.page_num}</span>
                  )}
                  {selected.source.material_id &&
                    data.materials.find(m => m.material_id === selected.source!.material_id)?.kind === 'file' && (
                    <button className={styles.pdfBtn} onClick={() => setPdfOpen(true)}>
                      📖 View in PDF
                    </button>
                  )}
                </span>
              </div>

              <div
                className={`${styles.verifyBar} ${
                  selected.source.sha256_verified ? styles.verifyOk : styles.verifyWarn
                }`}
              >
                {selected.source.sha256_verified ? (
                  <>🔒 GROUNDED — sha256 verified</>
                ) : (
                  <>⚠ Source linked, hash not re-verified</>
                )}
                {selected.source.sha256 && (
                  <code className={styles.hash}>{selected.source.sha256.slice(0, 24)}…</code>
                )}
              </div>

              <div className={styles.sourceBody}>
                <HighlightedChunk claim={selected} />
              </div>

              <div className={styles.sourceMeta}>
                {selected.source.char_start != null && selected.source.char_end != null && (
                  <span>
                    chars {selected.source.char_start}–{selected.source.char_end}
                  </span>
                )}
                <span>chunk {selected.source.chunk_id.slice(0, 8)}</span>
              </div>
            </div>
          ) : (
            <div className={styles.gapCard}>
              <div className={styles.gapIcon}>⚠</div>
              <h4 className={styles.gapTitle}>Evidence gap in your own writing</h4>
              <p className={styles.gapBody}>
                This reviewer is probing a point that <strong>isn&apos;t supported</strong> by any
                passage in your uploaded materials. In a real review, you&apos;d be asked to defend
                it with no source to fall back on. Strengthen the manuscript, or prepare an answer.
              </p>
              {selected.excerpt && (
                <p className={styles.gapExcerpt}>
                  Reviewer&apos;s note: <em>{selected.excerpt}</em>
                </p>
              )}
            </div>
          )}

          {selected?.grounded && selected.source && (
            <TrustComparison debateId={debateId} claim={selected} />
          )}

          <p className={styles.contrast}>
            Paste this same critique into a raw chatbot and ask “where&apos;s your source?” — it
            invents a page number. PeerForge shows the verified line, or admits the gap.
          </p>
        </section>
      </div>

      {pdfOpen && selected?.source?.material_id && (
        <PdfSourceViewer
          debateId={debateId}
          materialId={selected.source.material_id}
          docTitle={selected.source.doc_title}
          page={selected.source.page_num}
          highlightText={selected.excerpt || selected.source.chunk_text.slice(0, 300)}
          onClose={() => setPdfOpen(false)}
        />
      )}
    </div>
  );
}
