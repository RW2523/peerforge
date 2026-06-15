/**
 * Materials management hook for setup wizard
 */

import { useState, useCallback } from 'react';
import * as api from '@/lib/api';

export function useMaterials() {
  const [materials, setMaterials] = useState<api.SetupMaterial[]>([]);

  const handleAdd = useCallback((kind: 'text' | 'link' | 'file_placeholder') => {
    setMaterials(prev => [...prev, { kind, title: '', body_text: '', url: '' }]);
  }, []);

  const handleUpdate = useCallback((idx: number, updates: Partial<api.SetupMaterial>) => {
    setMaterials(prev => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], ...updates };
      return updated;
    });
  }, []);

  const handleRemove = useCallback((idx: number) => {
    setMaterials(prev => prev.filter((_, i) => i !== idx));
  }, []);

  return { materials, handleAdd, handleUpdate, handleRemove };
}
