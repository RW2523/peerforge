'use client';

/**
 * ReadinessCertificate — Pillar 3.
 *
 * Shows the trajectory of the ten academic dimensions across sessions, an
 * evidence ledger every score can be drilled into (dimension → the answers that
 * moved it → the question → the sha256-verified source line), and a tamper-
 * evident content-hash anchor. Exportable via the browser print dialog (→ PDF).
 */
import { useEffect, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { getCertificate, issueCertificate, ReadinessCertificate as Cert } from '@/lib/api';
import styles from './ReadinessCertificate.module.css';

interface Props {
  debateId: string;
}

const bandClass: Record<string, string> = {
  Strong: 'bandStrong',
  Competent: 'bandCompetent',
  Developing: 'bandDeveloping',
  'Under-prepared': 'bandUnder',
};

function DeltaTag({ delta }: { delta: number }) {
  if (delta > 0) return <span className={styles.deltaUp}>▲ +{delta.toFixed(1)}</span>;
  if (delta < 0) return <span className={styles.deltaDown}>▼ {delta.toFixed(1)}</span>;
  return <span className={styles.deltaFlat}>■ 0.0</span>;
}

export default function ReadinessCertificate({ debateId }: Props) {
  const [cert, setCert] = useState<(Cert & { issued?: boolean }) | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openDim, setOpenDim] = useState<string | null>(null);
  const [issued, setIssued] = useState(false);
  const [issuing, setIssuing] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    getCertificate(debateId)
      .then((c) => { if (alive) { setCert(c); setIssued(!!c.issued); } })
      .catch((e) => alive && setError(String(e?.message || e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [debateId]);

  const handleIssue = async () => {
    setIssuing(true);
    try {
      await issueCertificate(debateId);
      setIssued(true);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setIssuing(false);
    }
  };

  const verifyUrl = cert
    ? `${typeof window !== 'undefined' ? window.location.origin : ''}/verify/${cert.anchor.certificate_id}`
    : '';

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(verifyUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard unavailable — the URL is visible to select */ }
  };

  if (loading) return <div className={styles.state}>Assembling certificate…</div>;
  if (error) {
    return (
      <div className={styles.state}>
        <p>{error.includes('No assessment') || error.includes('assessments yet')
          ? 'No assessments yet. Run at least one Academic Assessment (Practice Q&A) to issue a certificate.'
          : `Could not build certificate: ${error}`}</p>
      </div>
    );
  }
  if (!cert) return null;

  const o = cert.overall;
  const answersById = new Map(cert.evidence.answers.map((a) => [a.category || '', a]));

  return (
    <div className={styles.wrap}>
      {/* Actions (hidden when printing) */}
      <div className={styles.actions}>
        {!issued ? (
          <button className={styles.issueBtn} onClick={handleIssue} disabled={issuing}>
            {issuing ? 'Signing…' : '🔏 Issue signed certificate'}
          </button>
        ) : (
          <div className={styles.shareRow}>
            <span className={styles.issuedBadge}>🔏 Signed &amp; issued</span>
            <code className={styles.shareUrl}>{verifyUrl}</code>
            <button className={styles.copyBtn} onClick={copyLink}>
              {copied ? '✓ Copied' : 'Copy verify link'}
            </button>
          </div>
        )}
        <button className={styles.printBtn} onClick={() => window.print()}>
          ⧉ Export / Print certificate
        </button>
      </div>

      <article className={styles.cert} id="pf-certificate">
        <header className={styles.head}>
          <div>
            <div className={styles.kicker}>PeerForge · Review-Readiness Certificate</div>
            <h2 className={styles.title}>{cert.session.title}</h2>
          </div>
          <div className={`${styles.overallBadge} ${styles[bandClass[o.band] || 'bandDeveloping']}`}>
            <span className={styles.overallScore}>{o.latest_score?.toFixed(1) ?? '—'}</span>
            <span className={styles.overallOf}>/10</span>
            <span className={styles.overallBand}>{o.band}</span>
          </div>
        </header>

        <div className={styles.summaryRow}>
          <div className={styles.summaryStat}>
            <span className={styles.sLbl}>Trajectory</span>
            <span className={styles.sVal}>
              {o.first_score?.toFixed(1)} → {o.latest_score?.toFixed(1)} <DeltaTag delta={o.delta} />
            </span>
          </div>
          <div className={styles.summaryStat}>
            <span className={styles.sLbl}>Assessments</span>
            <span className={styles.sVal}>{o.assessment_count}</span>
          </div>
          <div className={styles.summaryStat}>
            <span className={styles.sLbl}>Certificate ID</span>
            <span className={styles.sValMono}>{cert.certificate_id}</span>
          </div>
        </div>

        {/* Ten-dimension trajectory */}
        <h3 className={styles.sectionTitle}>Dimension trajectory</h3>
        <div className={styles.dims}>
          {cert.dimensions.map((d) => {
            const evidence = answersById.get(d.key);
            const open = openDim === d.key;
            return (
              <div key={d.key} className={styles.dimRow}>
                <button className={styles.dimHead} onClick={() => setOpenDim(open ? null : d.key)}>
                  <span className={styles.dimLabel}>{d.label}</span>
                  <span className={styles.dimTrack}>
                    <span
                      className={styles.dimFillFirst}
                      style={{ width: `${(d.first_score / 10) * 100}%` }}
                    />
                    <span
                      className={styles.dimFill}
                      style={{ width: `${(d.latest_score / 10) * 100}%` }}
                    />
                  </span>
                  <span className={styles.dimScores}>
                    {d.first_score.toFixed(1)} → <strong>{d.latest_score.toFixed(1)}</strong>{' '}
                    <DeltaTag delta={d.delta} />
                  </span>
                </button>
                {open && (
                  <div className={styles.drill}>
                    <p className={styles.dimWhat}>{d.what}</p>
                    <p className={styles.dimComment}>“{d.latest_comment}”</p>
                    {d.points.length > 1 && (
                      <div className={styles.points}>
                        {d.points.map((p, i) => (
                          <span key={i} className={styles.point}>
                            {p.score.toFixed(1)}
                            <em>{p.trigger?.replace(/_/g, ' ')}</em>
                          </span>
                        ))}
                      </div>
                    )}
                    {evidence && (
                      <div className={styles.evidenceLink}>
                        <div className={styles.evQ}>
                          <strong>{evidence.persona || 'Reviewer'}:</strong> {evidence.question_text}
                        </div>
                        {evidence.source?.excerpt && (
                          <div className={styles.evSrc}>
                            <span className={styles.evSrcQuote}>“{evidence.source.excerpt}”</span>
                            {evidence.source.sha256_verified && (
                              <span className={styles.verified}>🔒 sha256 verified</span>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Evidence ledger */}
        <h3 className={styles.sectionTitle}>Evidence ledger</h3>
        <p className={styles.ledgerNote}>
          {cert.evidence.answers.length} practice answer(s) and {cert.evidence.panel_events.count} panel
          contribution(s) underpin these scores. Each grounded answer links to a source line whose
          content hash is re-verified below.
        </p>
        <div className={styles.ledger}>
          {cert.evidence.answers.map((a) => (
            <div key={a.answer_id} className={styles.ledgerRow}>
              <div className={styles.ledgerTop}>
                <span className={styles.ledgerCat}>{(a.category || 'general').replace(/_/g, ' ')}</span>
                {a.answer_score != null && (
                  <span className={styles.ledgerScore}>{a.answer_score.toFixed(1)}/10</span>
                )}
                {a.source?.sha256_verified && <span className={styles.verified}>🔒 verified</span>}
              </div>
              <div className={styles.ledgerQ}>{a.question_text || '—'}</div>
              {a.source?.excerpt && <div className={styles.ledgerSrc}>Source: “{a.source.excerpt}”</div>}
            </div>
          ))}
        </div>

        {/* Tamper-evident anchor + public verification QR */}
        <footer className={styles.anchor}>
          <div className={styles.anchorGrid}>
            <div>
              <div className={styles.anchorTitle}>🔒 Tamper-evident anchor</div>
              <code className={styles.anchorHash}>
                {cert.anchor.algorithm}: {cert.anchor.hash}
              </code>
              <p className={styles.anchorNote}>
                This hash is computed over the scores, the ordered evidence entries, their source-chunk
                hashes and the session&apos;s append-only event span. Re-hashing the stored data
                reproduces it — altering any underlying evidence would not.
                {issued && ' The Ed25519-signed record can be independently verified at the link below.'}
                {' '}Issued {new Date(cert.issued_at).toLocaleString()}.
              </p>
              {issued && <div className={styles.verifyUrlPrint}>Verify at: {verifyUrl}</div>}
            </div>
            {issued && (
              <div className={styles.qrBlock}>
                <QRCodeSVG value={verifyUrl} size={92} marginSize={1} />
                <span className={styles.qrLabel}>Scan to verify</span>
              </div>
            )}
          </div>
        </footer>
      </article>
    </div>
  );
}
