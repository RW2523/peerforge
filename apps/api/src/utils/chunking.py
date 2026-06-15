"""
Text chunking utilities with provenance tracking
Paragraph-aware chunking with overlap for better retrieval
"""

import hashlib
from typing import List, Dict, Optional


class TextChunker:
    """Chunk text with provenance and overlap"""
    
    # Default chunk size (characters)
    DEFAULT_CHUNK_SIZE = 1000
    
    # Overlap between chunks (characters)
    DEFAULT_OVERLAP = 200
    
    @staticmethod
    def chunk_text(
        text: str,
        material_id: str,
        extraction_metadata: Dict,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP
    ) -> List[Dict]:
        """
        Chunk text with paragraph awareness and provenance
        
        Args:
            text: Full text to chunk
            material_id: Material UUID
            extraction_metadata: Metadata from text extraction
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks in characters
        
        Returns:
            List of chunk dictionaries with provenance
        """
        if not text or not text.strip():
            return []
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_index = 0
        char_offset = 0
        
        for para_idx, para in enumerate(paragraphs):
            para_len = len(para)
            
            # If single paragraph exceeds chunk size, split it
            if para_len > chunk_size:
                # Commit current chunk if exists
                if current_chunk:
                    chunks.append(TextChunker._create_chunk(
                        chunk_index=chunk_index,
                        text='\n\n'.join(current_chunk),
                        material_id=material_id,
                        char_start=char_offset - current_size,
                        char_end=char_offset,
                        extraction_metadata=extraction_metadata
                    ))
                    chunk_index += 1
                    current_chunk = []
                    current_size = 0
                
                # Split long paragraph
                para_chunks = TextChunker._split_long_paragraph(para, chunk_size, overlap)
                for sub_text in para_chunks:
                    chunks.append(TextChunker._create_chunk(
                        chunk_index=chunk_index,
                        text=sub_text,
                        material_id=material_id,
                        char_start=char_offset,
                        char_end=char_offset + len(sub_text),
                        extraction_metadata=extraction_metadata
                    ))
                    chunk_index += 1
                    char_offset += len(sub_text)
                
                continue
            
            # Check if adding this paragraph exceeds chunk size
            if current_size + para_len > chunk_size and current_chunk:
                # Commit current chunk
                chunks.append(TextChunker._create_chunk(
                    chunk_index=chunk_index,
                    text='\n\n'.join(current_chunk),
                    material_id=material_id,
                    char_start=char_offset - current_size,
                    char_end=char_offset,
                    extraction_metadata=extraction_metadata
                ))
                chunk_index += 1
                
                # Handle overlap: keep last paragraph if it fits in overlap
                if current_chunk and len(current_chunk[-1]) <= overlap:
                    current_chunk = [current_chunk[-1]]
                    current_size = len(current_chunk[-1]) + 2  # +2 for \n\n
                else:
                    current_chunk = []
                    current_size = 0
            
            current_chunk.append(para)
            current_size += para_len + 2  # +2 for \n\n separator
            char_offset += para_len + 2
        
        # Commit final chunk
        if current_chunk:
            chunks.append(TextChunker._create_chunk(
                chunk_index=chunk_index,
                text='\n\n'.join(current_chunk),
                material_id=material_id,
                char_start=char_offset - current_size,
                char_end=char_offset,
                extraction_metadata=extraction_metadata
            ))
        
        return chunks
    
    @staticmethod
    def _split_long_paragraph(text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split a single long paragraph into multiple chunks"""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            
            # Try to break at sentence boundary
            if end < text_len:
                # Look for sentence endings
                for punct in ['. ', '! ', '? ', '\n']:
                    last_punct = text.rfind(punct, start, end)
                    if last_punct > start + chunk_size // 2:  # At least halfway through
                        end = last_punct + len(punct)
                        break
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)
            
            # Move start with overlap
            start = max(start + chunk_size - overlap, end)
        
        return chunks
    
    @staticmethod
    def _create_chunk(
        chunk_index: int,
        text: str,
        material_id: str,
        char_start: int,
        char_end: int,
        extraction_metadata: Dict
    ) -> Dict:
        """
        Create chunk dictionary with provenance metadata
        
        Returns:
            {
                'chunk_text': str,
                'chunk_metadata': {
                    'material_id': str,
                    'chunk_index': int,
                    'char_start': int,
                    'char_end': int,
                    'word_count': int,
                    'sha256': str,
                    'extraction_method': str,
                    'page_num': Optional[int],  # For PDFs
                    'paragraph_num': Optional[int],  # For DOCX
                }
            }
        """
        word_count = len(text.split())
        sha256 = hashlib.sha256(text.encode('utf-8')).hexdigest()
        
        metadata = {
            'material_id': material_id,
            'chunk_index': chunk_index,
            'char_start': char_start,
            'char_end': char_end,
            'word_count': word_count,
            'sha256': sha256,
            'extraction_method': extraction_metadata.get('extraction_method', 'unknown'),
        }
        
        # Add page number for PDFs (estimate based on char position)
        if extraction_metadata.get('pages'):
            # Find which page this chunk primarily belongs to
            chunk_mid = (char_start + char_end) // 2
            for page in extraction_metadata['pages']:
                if page['char_start'] <= chunk_mid <= page['char_end']:
                    metadata['page_num'] = page['page_num']
                    break
        
        # Add paragraph number for DOCX (estimate based on char position)
        if extraction_metadata.get('paragraphs'):
            chunk_mid = (char_start + char_end) // 2
            for para in extraction_metadata['paragraphs']:
                if para['char_start'] <= chunk_mid <= para['char_end']:
                    metadata['paragraph_num'] = para['paragraph_num']
                    break
        
        return {
            'chunk_text': text,
            'chunk_metadata': metadata
        }
    
    @staticmethod
    def generate_chunk_id(material_id: str, chunk_index: int) -> str:
        """
        Generate stable chunk ID
        Format: material_id + chunk_index hash
        """
        combined = f"{material_id}:{chunk_index}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
