"""
Tests for materials ingestion pipeline (TICKET-12)
End-to-end tests with real DB, MinIO, and Celery task execution
"""

import os
import io
import psycopg2
from fastapi.testclient import TestClient
from src.main import app
from src.config import settings
from src.tasks.material_processing import process_material

client = TestClient(app)

# Test fixture path
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
SAMPLE_TXT_PATH = os.path.join(FIXTURES_DIR, 'sample.txt')


def test_materials_upload_and_process_e2e():
    """
    End-to-end test: Upload file -> Process -> Verify chunks with provenance
    
    Flow:
    1. Create a debate
    2. Upload sample.txt via POST /materials/upload
    3. Execute Celery task directly (same code worker runs)
    4. Verify material status is 'complete'
    5. Verify memory_chunks exist with correct provenance metadata
    6. Verify GET /materials/status returns complete status
    """
    # 1. Create debate
    create_response = client.post(
        "/debates",
        json={
            "workspace_id": "00000000-0000-0000-0000-000000000101",
            "title": "Materials Ingestion Test Debate"
        }
    )
    assert create_response.status_code == 201
    debate_id = create_response.json()["debate_id"]
    
    # 2. Upload sample.txt
    with open(SAMPLE_TXT_PATH, 'rb') as f:
        file_contents = f.read()
    
    files = {'files': ('sample.txt', io.BytesIO(file_contents), 'text/plain')}
    
    upload_response = client.post(
        f"/debates/{debate_id}/materials/upload",
        files=files
    )
    assert upload_response.status_code == 200
    upload_data = upload_response.json()
    
    assert 'material_ids' in upload_data
    assert 'job_ids' in upload_data
    assert len(upload_data['material_ids']) == 1
    assert len(upload_data['job_ids']) == 1
    
    material_id = upload_data['material_ids'][0]
    
    # Verify material row created with kind='file', status='pending'
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT kind, file_key, file_size_bytes, file_mime_type, processed_status
        FROM meeting_materials
        WHERE material_id = %s
    """, (material_id,))
    result = cursor.fetchone()
    conn.close()
    
    assert result is not None
    kind, file_key, file_size_bytes, file_mime_type, processed_status = result
    assert kind == 'file'
    assert file_key is not None
    assert file_size_bytes > 0
    assert file_mime_type == 'text/plain'
    assert processed_status in ['pending', 'processing']  # May already be processing
    
    # 3. Execute Celery task directly (same code the worker runs)
    # This processes the material synchronously for testing
    result = process_material(material_id, debate_id)
    
    assert result['status'] == 'complete'
    assert result['chunk_count'] > 0
    assert result['word_count'] > 0
    
    # 4. Verify material status is 'complete'
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT processed_status, processing_metadata
        FROM meeting_materials
        WHERE material_id = %s
    """, (material_id,))
    status_result = cursor.fetchone()
    
    assert status_result is not None
    processed_status, processing_metadata = status_result
    assert processed_status == 'complete'
    assert processing_metadata is not None
    assert 'word_count' in processing_metadata
    assert 'chunk_count' in processing_metadata
    assert processing_metadata['word_count'] > 0
    assert processing_metadata['chunk_count'] > 0
    
    # 5. Verify memory_chunks exist with provenance.
    # A live Celery worker may process the same queued upload concurrently with
    # the synchronous call above; processing is idempotent, so poll briefly
    # until the chunk set settles instead of racing the worker.
    import time
    chunks = []
    for _ in range(10):
        cursor.execute("""
            SELECT chunk_id, chunk_text, chunk_metadata, agent_id, source_debate_id
            FROM memory_chunks
            WHERE chunk_metadata->>'material_id' = %s
            ORDER BY (chunk_metadata->>'chunk_index')::int
        """, (material_id,))
        chunks = cursor.fetchall()
        if len(chunks) == processing_metadata['chunk_count']:
            break
        conn.rollback()  # fresh snapshot for the next poll
        time.sleep(1)
    conn.close()

    assert len(chunks) > 0, "No chunks created"
    assert len(chunks) == processing_metadata['chunk_count']
    
    # Verify chunk provenance
    for chunk in chunks:
        chunk_id, chunk_text, chunk_metadata, agent_id, source_debate_id = chunk
        
        # Material chunks have agent_id=NULL
        assert agent_id is None
        
        # Must have source_debate_id
        assert source_debate_id == debate_id
        
        # Must have text content
        assert chunk_text is not None
        assert len(chunk_text) > 0
        
        # Must have provenance metadata
        assert chunk_metadata is not None
        assert 'material_id' in chunk_metadata
        assert 'chunk_index' in chunk_metadata
        assert 'char_start' in chunk_metadata
        assert 'char_end' in chunk_metadata
        assert 'word_count' in chunk_metadata
        assert 'sha256' in chunk_metadata
        assert 'extraction_method' in chunk_metadata
        
        assert chunk_metadata['material_id'] == material_id
        assert chunk_metadata['extraction_method'] == 'plain_text'
    
    # 6. Verify GET /materials/status returns complete status
    status_response = client.get(f"/debates/{debate_id}/materials/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    
    assert status_data['debate_id'] == debate_id
    assert status_data['total_materials'] == 1
    assert 'complete' in status_data['status_summary']
    assert status_data['status_summary']['complete'] == 1
    
    assert len(status_data['materials']) == 1
    material_status = status_data['materials'][0]
    assert material_status['material_id'] == material_id
    assert material_status['kind'] == 'file'
    assert material_status['processed_status'] == 'complete'
    assert material_status['processing_metadata']['chunk_count'] > 0
    assert material_status['processing_metadata']['word_count'] > 0


def test_materials_upload_invalid_file_type():
    """Test that invalid file types are rejected"""
    # Create debate
    create_response = client.post(
        "/debates",
        json={
            "workspace_id": "00000000-0000-0000-0000-000000000101",
            "title": "Invalid File Test"
        }
    )
    assert create_response.status_code == 201
    debate_id = create_response.json()["debate_id"]
    
    # Try to upload file with invalid extension and content
    fake_exe = b'MZ\x90\x00\x03\x00\x00\x00'  # Looks like exe header
    files = {'files': ('virus.exe', io.BytesIO(fake_exe), 'application/x-msdownload')}
    
    upload_response = client.post(
        f"/debates/{debate_id}/materials/upload",
        files=files
    )
    
    # Should reject with 400
    assert upload_response.status_code == 400
    assert 'validation failed' in upload_response.json()['detail'].lower()


def test_materials_upload_file_too_large():
    """Test that files exceeding size limit are rejected"""
    # Create debate
    create_response = client.post(
        "/debates",
        json={
            "workspace_id": "00000000-0000-0000-0000-000000000101",
            "title": "Large File Test"
        }
    )
    assert create_response.status_code == 201
    debate_id = create_response.json()["debate_id"]
    
    # Create file larger than 50MB limit
    large_content = b'A' * (51 * 1024 * 1024)  # 51MB
    files = {'files': ('large.txt', io.BytesIO(large_content), 'text/plain')}
    
    upload_response = client.post(
        f"/debates/{debate_id}/materials/upload",
        files=files
    )
    
    # Should reject with 400
    assert upload_response.status_code == 400
    assert 'size exceeds' in upload_response.json()['detail'].lower()
