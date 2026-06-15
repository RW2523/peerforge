'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import * as api from '@/lib/api';
import styles from './UserMenu.module.css';

export default function UserMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const [credits, setCredits] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { apiKey, hasKey } = useOpenRouterKey();

  // Only show credit widget after mounting to avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (hasKey && apiKey) {
      fetchCredits();
    }
  }, [hasKey, apiKey]);

  const fetchCredits = async () => {
    if (!apiKey) return;
    
    setLoading(true);
    try {
      const accountData = await api.getOpenRouterAccount(apiKey);
      
      if (accountData.credits?.balance !== undefined) {
        setCredits(accountData.credits.balance);
      } else if (accountData.key?.usage !== undefined && accountData.key?.limit) {
        // Calculate remaining from usage/limit
        setCredits(accountData.key.limit - accountData.key.usage);
      } else {
        setCredits(null);
      }
    } catch (error) {
      console.error('Failed to fetch credits:', error);
      setCredits(null);
    } finally {
      setLoading(false);
    }
  };

  const handleNavigate = (path: string) => {
    setIsOpen(false);
    router.push(path);
  };

  return (
    <div className={styles.userMenu} ref={menuRef}>
      {/* Credit Widget - only render after mount to avoid hydration mismatch */}
      {mounted && hasKey && (
        <div className={styles.creditWidget}>
          {loading ? (
            <span className={styles.creditLoading}>...</span>
          ) : credits !== null ? (
            <>
              <span className={styles.creditIcon}>💳</span>
              <span className={styles.creditAmount}>${credits.toFixed(2)}</span>
            </>
          ) : (
            <span className={styles.creditNA}>API Connected</span>
          )}
        </div>
      )}

      {/* Menu Button */}
      <button
        className={styles.menuButton}
        onClick={() => setIsOpen(!isOpen)}
        aria-label="User menu"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="4" r="1.5" fill="currentColor" />
          <circle cx="10" cy="10" r="1.5" fill="currentColor" />
          <circle cx="10" cy="16" r="1.5" fill="currentColor" />
        </svg>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className={styles.dropdown}>
          <button
            className={styles.menuItem}
            onClick={() => handleNavigate('/settings')}
          >
            <span className={styles.menuIcon}>⚙️</span>
            <span>Settings</span>
          </button>
          
          <button
            className={styles.menuItem}
            onClick={() => handleNavigate('/history')}
          >
            <span className={styles.menuIcon} />
            <span>History</span>
          </button>

          <div className={styles.divider} />

          <button
            className={styles.menuItem}
            onClick={() => handleNavigate('/login')}
          >
            <span className={styles.menuIcon}>👤</span>
            <span>Account</span>
          </button>

          <button
            className={styles.menuItem}
            onClick={() => handleNavigate('/logout')}
          >
            <span className={styles.menuIcon}>🚪</span>
            <span>Logout</span>
          </button>
        </div>
      )}
    </div>
  );
}
