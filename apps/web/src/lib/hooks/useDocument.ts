/**
 * useDocument Hook - Document state management
 */
import { useState, useEffect, useCallback } from 'react';
import { Document, DocumentSection, CreateDocumentRequest } from '../document/types';
import * as api from '../api';

export function useDocument(documentId?: string) {
  const [document, setDocument] = useState<Document | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDocument = useCallback(async () => {
    if (!documentId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const data = await api.getDocument(documentId);
      setDocument(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch document');
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  const createDocument = useCallback(async (request: CreateDocumentRequest) => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await api.createDocument(request);
      setDocument(data);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create document');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSection = useCallback((sectionId: string, updates: Partial<DocumentSection>) => {
    setDocument(prev => {
      if (!prev) return prev;
      
      return {
        ...prev,
        sections: prev.sections.map(section =>
          section.id === sectionId ? { ...section, ...updates } : section
        ),
      };
    });
  }, []);

  useEffect(() => {
    if (documentId) {
      fetchDocument();
    }
  }, [documentId, fetchDocument]);

  return {
    document,
    loading,
    error,
    createDocument,
    updateSection,
    refetch: fetchDocument,
  };
}
