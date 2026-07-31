'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import UserMenu from './UserMenu';
import WorkspaceSwitcher from './WorkspaceSwitcher';
import ThemeToggle from './ThemeToggle';
import { APP_NAME, APP_TAGLINE, APP_ICON } from '@/lib/brand';
import styles from './AppNav.module.css';

export default function AppNav() {
  const pathname = usePathname();

  const isActive = (path: string) => {
    if (path === '/') return pathname === '/';
    return pathname.startsWith(path);
  };

  return (
    <nav className={styles.nav} aria-label="Main">
      <div className={styles.container}>
        <Link href="/" className={styles.logo}>
          <span className={styles.logoIcon}>{APP_ICON}</span>
          <div className={styles.logoText}>
            <span className={styles.wordmark}>{APP_NAME}</span>
            <span className={styles.tagline}>{APP_TAGLINE}</span>
          </div>
        </Link>

        <div className={styles.navRight}>
          <WorkspaceSwitcher />
          <div className={styles.links}>
            <Link
              href="/"
              className={`${styles.link} ${isActive('/') && !pathname.includes('/room') && !pathname.includes('/setup') && !pathname.includes('/settings') && !pathname.includes('/history') ? styles.active : ''}`}
              aria-current={isActive('/') ? 'page' : undefined}
            >
              Home
            </Link>
            <Link
              href="/setup/chat"
              className={`${styles.link} ${isActive('/setup/chat') ? styles.active : ''}`}
              aria-current={isActive('/setup/chat') ? 'page' : undefined}
            >
              New Session
            </Link>
            <Link
              href="/setup"
              className={`${styles.link} ${isActive('/setup') && !isActive('/setup/chat') ? styles.active : ''}`}
              aria-current={isActive('/setup') ? 'page' : undefined}
            >
              Advanced Setup
            </Link>
            <Link
              href="/room"
              className={`${styles.link} ${isActive('/room') ? styles.active : ''}`}
              aria-current={isActive('/room') ? 'page' : undefined}
            >
              Review Room
            </Link>
            <Link
              href="/history"
              className={`${styles.link} ${isActive('/history') ? styles.active : ''}`}
              aria-current={isActive('/history') ? 'page' : undefined}
            >
              History
            </Link>
            <Link
              href="/progress"
              className={`${styles.link} ${isActive('/progress') ? styles.active : ''}`}
              aria-current={isActive('/progress') ? 'page' : undefined}
            >
              Progress
            </Link>
            <Link
              href="/cohort"
              className={`${styles.link} ${isActive('/cohort') ? styles.active : ''}`}
              aria-current={isActive('/cohort') ? 'page' : undefined}
            >
              Cohort
            </Link>            <Link
              href="/organization"
              className={`${styles.link} ${isActive('/organization') ? styles.active : ''}`}
              aria-current={isActive('/organization') ? 'page' : undefined}
            >
              Organization
            </Link>
          </div>

          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </nav>
  );
}
