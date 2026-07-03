'use client';

/**
 * PdfSourceViewer — Pillar 1's 60-second wow, made literal.
 *
 * Renders the researcher's ACTUAL uploaded PDF (streamed from object storage),
 * jumps to the page the verified chunk came from, and highlights the text-layer
 * lines that belong to the quoted excerpt. Every text item on the page whose
 * content appears inside the verified excerpt gets a <mark> wrap — so the
 * evidence lights up on the real manuscript, not a paraphrase.
 */
import { useCallback, useMemo, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/TextLayer.css';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import styles from './PdfSourceViewer.module.css';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.js',
  import.meta.url,
).toString();

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Props {
  debateId: string;
  materialId: string;
  docTitle: string;
  /** 1-based page number recorded at ingest. */
  page: number | null;
  /** The verified excerpt to light up on the page. */
  highlightText: string;
  onClose: () => void;
}

function normalize(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

// react-pdf injects customTextRenderer output as HTML — escape the PDF's own
// text so a crafted document can't smuggle markup into the text layer.
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export default function PdfSourceViewer({
  debateId, materialId, docTitle, page, highlightText, onClose,
}: Props) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNum, setPageNum] = useState(Math.max(1, page ?? 1));
  const [error, setError] = useState<string | null>(null);

  const fileUrl = `${API_URL}/debates/${debateId}/materials/${materialId}/file`;
  const normExcerpt = useMemo(() => normalize(highlightText), [highlightText]);
  const excerptWords = useMemo(
    () => new Set(normExcerpt.split(' ').filter(w => w.length > 2)),
    [normExcerpt],
  );

  // Wrap the text-layer lines that carry the verified excerpt. PDF lines
  // rarely align with excerpt boundaries, so a line matches when it is either
  // contained in the excerpt or shares most of its words with it.
  const customTextRenderer = useCallback(
    ({ str }: { str: string }) => {
      const safe = escapeHtml(str);
      const norm = normalize(str);
      if (norm.length >= 12 && normExcerpt.includes(norm)) {
        return `<mark class="${styles.pdfMark}">${safe}</mark>`;
      }
      const words = norm.split(' ').filter(w => w.length > 2);
      if (words.length >= 4) {
        const hits = words.filter(w => excerptWords.has(w)).length;
        if (hits / words.length >= 0.6) {
          return `<mark class="${styles.pdfMark}">${safe}</mark>`;
        }
      }
      return safe;
    },
    [normExcerpt, excerptWords],
  );

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <header className={styles.head}>
          <div>
            <div className={styles.title}>📄 {docTitle}</div>
            <div className={styles.subtitle}>
              Verified passage highlighted on the original manuscript
              {page != null && ` — page ${page}`}
            </div>
          </div>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </header>

        <div className={styles.body}>
          {error ? (
            <div className={styles.error}>Could not render PDF: {error}</div>
          ) : (
            <Document
              file={fileUrl}
              onLoadSuccess={({ numPages: n }) => setNumPages(n)}
              onLoadError={(e) => setError(e?.message || 'load failed')}
              loading={<div className={styles.loading}>Loading manuscript…</div>}
            >
              <Page
                pageNumber={Math.min(pageNum, numPages ?? pageNum)}
                width={760}
                customTextRenderer={customTextRenderer}
                renderAnnotationLayer={false}
              />
            </Document>
          )}
        </div>

        <footer className={styles.foot}>
          <button
            className={styles.navBtn}
            disabled={pageNum <= 1}
            onClick={() => setPageNum(p => p - 1)}
          >
            ← Prev
          </button>
          <span className={styles.pageInfo}>
            Page {pageNum}{numPages ? ` of ${numPages}` : ''}
          </span>
          <button
            className={styles.navBtn}
            disabled={numPages != null && pageNum >= numPages}
            onClick={() => setPageNum(p => p + 1)}
          >
            Next →
          </button>
        </footer>
      </div>
    </div>
  );
}
