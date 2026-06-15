'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import UserMenu from './UserMenu';
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
    <nav className={styles.nav}>
      <div className={styles.container}>
        <Link href="/" className={styles.logo}>
          <span className={styles.logoIcon}>{APP_ICON}</span>
          <div className={styles.logoText}>
            <span className={styles.wordmark}>{APP_NAME}</span>
            <span className={styles.tagline}>{APP_TAGLINE}</span>
          </div>
        </Link>

        <div className={styles.navRight}>
          <div className={styles.links}>
            <Link
              href="/"
              className={`${styles.link} ${isActive('/') && !pathname.includes('/room') && !pathname.includes('/setup') && !pathname.includes('/settings') && !pathname.includes('/history') ? styles.active : ''}`}
            >
              Home
            </Link>
            <Link
              href="/setup"
              className={`${styles.link} ${isActive('/setup') ? styles.active : ''}`}
            >
              New Session
            </Link>
            <Link
              href="/room"
              className={`${styles.link} ${isActive('/room') ? styles.active : ''}`}
            >
              Review Room
            </Link>
            <Link
              href="/history"
              className={`${styles.link} ${isActive('/history') ? styles.active : ''}`}
            >
              History
            </Link>
          </div>

          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </nav>
  );
}
