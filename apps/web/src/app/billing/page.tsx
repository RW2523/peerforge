'use client';

/**
 * Billing — plan & usage (paywall).
 *
 * Shows the workspace's current plan, live usage against its limits, and the
 * full tier ladder. Owners can switch plans: when payment is configured a paid
 * upgrade opens Stripe Checkout; otherwise the switch is self-serve.
 */
import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import {
  BillingInfo,
  changePlan,
  getBilling,
  openBillingPortal,
  Plan,
  startCheckout,
} from '@/lib/api';
import { useMe } from '@/lib/workspace';
import styles from './billing.module.css';

const STATUS_LABEL: Record<string, string> = {
  active: 'Active',
  canceling: 'Cancels at period end',
  canceled: 'Canceled',
  past_due: 'Payment past due',
};

const FEATURE_ROWS: { key: keyof Plan['features']; label: string }[] = [
  { key: 'presentation_coach', label: 'Presentation coach' },
  { key: 'certificates', label: 'Readiness certificates' },
  { key: 'advisor_console', label: 'Advisor console' },
  { key: 'departments', label: 'Departments' },
  { key: 'invites', label: 'Member invites' },
  { key: 'sso', label: 'Single sign-on' },
];

function limitText(n: number | null): string {
  return n === null ? 'Unlimited' : String(n);
}

export default function BillingPage() {
  const { me, workspaceId } = useMe();
  const search = useSearchParams();
  const [info, setInfo] = useState<BillingInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const isOwner = me?.role === 'owner' || me?.role === 'admin';

  const load = useCallback(() => {
    getBilling(workspaceId)
      .then(setInfo)
      .catch((e) => setError(String(e?.message || e)));
  }, [workspaceId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (search.get('upgraded')) setNotice('Payment complete — your plan is now active.');
  }, [search]);

  const handlePortal = async () => {
    setError(null);
    try {
      const url = await openBillingPortal(workspaceId);
      window.location.href = url;
    } catch (e) {
      setError(String((e as Error)?.message || e));
    }
  };

  const handleSelect = async (target: Plan) => {
    if (!info || busy) return;
    setError(null);
    setNotice(null);
    setBusy(target.plan);
    try {
      const isUpgrade = target.rank > info.current.rank;
      if (info.payment_enabled && isUpgrade && target.plan !== 'community') {
        const url = await startCheckout(workspaceId, target.plan);
        window.location.href = url;
        return;
      }
      await changePlan(workspaceId, target.plan);
      setNotice(`Plan changed to ${target.label}.`);
      load();
    } catch (e) {
      setError(String((e as Error)?.message || e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>Plan &amp; billing</h1>
          <p className={styles.subtitle}>
            Manage this workspace&apos;s plan. Limits are enforced as you create review sessions and add materials.
          </p>
        </header>

        {notice && <div className={styles.notice}>{notice}</div>}
        {error && <div className={styles.error}>{error}</div>}

        {!info ? (
          <div className={styles.state}>{error ? 'Could not load billing.' : 'Loading plan…'}</div>
        ) : (
          <>
            {info.subscription?.status && info.subscription.status !== 'active' && (
              <div className={`${styles.subBanner} ${info.subscription.status === 'past_due' ? styles.subBannerWarn : ''}`}>
                <span>
                  {STATUS_LABEL[info.subscription.status] || info.subscription.status}
                  {info.subscription.renews_at && info.subscription.status === 'canceling' &&
                    ` — access continues until ${new Date(info.subscription.renews_at).toLocaleDateString()}`}
                  {info.subscription.status === 'past_due' && ' — update your card to keep your plan.'}
                </span>
                {info.subscription.has_subscription && (
                  <button className={styles.manageInline} onClick={handlePortal}>Manage subscription →</button>
                )}
              </div>
            )}

            <section className={styles.usageBar}>
              <div className={styles.usageItem}>
                <span className={styles.usageLabel}>Current plan</span>
                <span className={styles.usageValue}>{info.current.label}</span>
                {info.subscription?.status === 'active' && info.subscription.renews_at && (
                  <span className={styles.renews}>Renews {new Date(info.subscription.renews_at).toLocaleDateString()}</span>
                )}
              </div>
              <div className={styles.usageItem}>
                <span className={styles.usageLabel}>Review sessions</span>
                <span className={styles.usageValue}>
                  {info.usage.sessions.used}
                  {' / '}
                  {limitText(info.usage.sessions.limit)}
                </span>
                {info.usage.sessions.limit !== null && (
                  <div className={styles.meter}>
                    <div
                      className={styles.meterFill}
                      style={{
                        width: `${Math.min(100, Math.round((info.usage.sessions.used / info.usage.sessions.limit) * 100))}%`,
                      }}
                    />
                  </div>
                )}
              </div>
              <div className={styles.usageItem}>
                <span className={styles.usageLabel}>Materials / session</span>
                <span className={styles.usageValue}>{limitText(info.usage.materials_per_session_limit)}</span>
              </div>
            </section>

            {isOwner && info.subscription?.has_subscription && (
              <div className={styles.manageRow}>
                <button className={styles.manageBtn} onClick={handlePortal}>Manage subscription</button>
                <span className={styles.manageHint}>Update your card, change plan, or cancel in the Stripe portal.</span>
              </div>
            )}
            {!isOwner && (
              <p className={styles.ownerNote}>Only a workspace owner can change the plan.</p>
            )}

            <section className={styles.cards}>
              {info.plans.map((p) => {
                const isCurrent = p.plan === info.current.plan;
                const isUpgrade = p.rank > info.current.rank;
                return (
                  <div key={p.plan} className={`${styles.card} ${isCurrent ? styles.cardCurrent : ''}`}>
                    <div className={styles.cardHead}>
                      <span className={styles.planName}>{p.label}</span>
                      {isCurrent && <span className={styles.badge}>Current</span>}
                    </div>
                    <div className={styles.price}>{p.price_hint}</div>
                    <p className={styles.blurb}>{p.blurb}</p>
                    <ul className={styles.featureList}>
                      <li><strong>{limitText(p.limits.max_sessions)}</strong> review sessions</li>
                      <li><strong>{limitText(p.limits.max_materials_per_session)}</strong> materials / session</li>
                      {FEATURE_ROWS.map((f) => (
                        <li key={f.key} className={p.features[f.key] ? styles.on : styles.off}>
                          {p.features[f.key] ? '✓' : '—'} {f.label}
                        </li>
                      ))}
                    </ul>
                    <button
                      className={`${styles.cta} ${isUpgrade ? styles.ctaUpgrade : ''}`}
                      disabled={isCurrent || !isOwner || !!busy}
                      onClick={() => handleSelect(p)}
                    >
                      {isCurrent
                        ? 'Your plan'
                        : busy === p.plan
                          ? 'Working…'
                          : info.payment_enabled && isUpgrade && p.plan !== 'community'
                            ? 'Upgrade →'
                            : isUpgrade ? 'Switch →' : 'Downgrade'}
                    </button>
                  </div>
                );
              })}
            </section>

            {!info.payment_enabled && (
              <p className={styles.footNote}>
                Payment isn&apos;t configured on this deployment, so plan changes apply immediately
                (trials / manual provisioning). Configure Stripe to require checkout for paid tiers.
              </p>
            )}
          </>
        )}
      </main>
    </>
  );
}
