'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { signOut } from '@/lib/supabase';
import styles from './logout.module.css';

export default function LogoutPage() {
  const [status, setStatus] = useState('Signing out...');
  const router = useRouter();

  useEffect(() => {
    const handleLogout = async () => {
      try {
        await signOut();
        setStatus('Signed out successfully');
        setTimeout(() => {
          router.push('/login');
        }, 1000);
      } catch (err: any) {
        setStatus(`Error: ${err.message}`);
      }
    };

    handleLogout();
  }, [router]);

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1>Logging Out</h1>
        <p className={styles.status}>{status}</p>
      </div>
    </div>
  );
}
