'use client';

/**
 * Public certificate verification — /verify/{certificate_id}
 *
 * No login required. A relying party (grad school, advisor, journal) opens the
 * link (or scans the QR on the printed certificate) and sees four live checks:
 * Ed25519 signature validity, hash integrity of the issued payload, and
 * whether the session's evidence still recomputes to the anchored hash.
 * Readiness summary only — no manuscript content is exposed here.
 */
import { use, useEffect, useState } from 'react';
import { getCertificateVerification, CertificateVerification } from '@/lib/api';
import styles from './verify.module.css';

function Check({ ok, label, detail }: { ok: boolean | null; label: string; detail: string }) {
  const cls = ok === true ? styles.checkOk : ok === false ? styles.checkFail : styles.checkNa;
  const icon = ok === true ? '✓' : ok === false ? '✕' : '—';
  return (
    <div className={`${styles.check} ${cls}`}>
      <span className={styles.checkIcon}>{icon}</span>
      <div>
        <div className={styles.checkLabel}>{label}</div>
        <div className={styles.checkDetail}>{detail}</div>
      </div>
    </div>
  );
}

export default function VerifyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<CertificateVerification | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCertificateVerification(id)
      .then(setData)
      .catch((e) => setError(String(e?.message || e)));
  }, [id]);

  if (error) {
    return (
      <main className={styles.page}>
        <div className={styles.card}>
          <h1 className={styles.brand}>🎓 PeerForge — Certificate Verification</h1>
          <p className={styles.error}>
            {error.includes('not found')
              ? `No certificate found for “${id}”. Check the ID on the printed certificate.`
              : `Verification failed: ${error}`}
          </p>
        </div>
      </main>
    );
  }
  if (!data) return <main className={styles.page}><div className={styles.card}>Verifying…</div></main>;

  const { checks, summary } = data;
  const valid = data.verdict === 'VALID';

  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <h1 className={styles.brand}>🎓 PeerForge — Certificate Verification</h1>

        <div className={`${styles.verdict} ${valid ? styles.verdictOk : styles.verdictBad}`}>
          {valid ? '✓ CERTIFICATE VALID' : '✕ CERTIFICATE INVALID'}
        </div>

        <div className={styles.meta}>
          <div><span className={styles.metaLbl}>Certificate</span><code>{data.certificate_id}</code></div>
          <div><span className={styles.metaLbl}>Issued</span>{new Date(data.issued_at).toLocaleString()}</div>
          <div><span className={styles.metaLbl}>Algorithm</span>{data.algorithm}</div>
        </div>

        <h2 className={styles.sectionTitle}>Integrity checks</h2>
        <div className={styles.checks}>
          <Check
            ok={checks.signature_valid}
            label="Signature authentic"
            detail="Ed25519 signature over the anchored evidence payload verifies against the platform key."
          />
          <Check
            ok={checks.hash_matches_payload}
            label="Anchor hash intact"
            detail="sha256 of the issued payload still equals the recorded anchor hash."
          />
          <Check
            ok={checks.live_check_available ? checks.evidence_unchanged_since_issue : null}
            label="Evidence unchanged since issue"
            detail={checks.live_check_available
              ? 'The session’s live assessments, answers, and event span recompute to the same hash.'
              : 'Live session data unavailable — the signed record above still stands on its own.'}
          />
        </div>

        <h2 className={styles.sectionTitle}>Certified readiness</h2>
        <div className={styles.summaryHead}>
          <div className={styles.sessionTitle}>{summary.title}</div>
          <div className={styles.band}>{summary.overall.band}</div>
        </div>
        <p className={styles.trajectory}>
          Overall {summary.overall.first_score?.toFixed(1)} → <strong>{summary.overall.latest_score?.toFixed(1)}</strong>/10
          {' '}across {summary.overall.assessment_count} assessment(s), grounded in{' '}
          {summary.evidence_counts.answers} evaluated answer(s) and {summary.evidence_counts.panel_events} panel contribution(s).
        </p>
        <div className={styles.dims}>
          {summary.dimensions.map((d) => (
            <div key={d.key} className={styles.dimRow}>
              <span className={styles.dimLabel}>{d.label}</span>
              <span className={styles.dimScores}>
                {d.first_score.toFixed(1)} → {d.latest_score.toFixed(1)}
                <em className={d.delta >= 0 ? styles.up : styles.down}>
                  {d.delta >= 0 ? ` ▲+${d.delta.toFixed(1)}` : ` ▼${d.delta.toFixed(1)}`}
                </em>
              </span>
            </div>
          ))}
        </div>

        <footer className={styles.foot}>
          <div>Anchor: <code className={styles.hash}>{data.anchor_hash}</code></div>
          <p>
            This page recomputed every check just now — nothing here is a stored badge. The anchor
            binds the scores to the exact evidence and the session&apos;s append-only event history.
          </p>
        </footer>
      </div>
    </main>
  );
}
