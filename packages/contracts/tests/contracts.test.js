/**
 * Contract validation tests
 * Lightweight tests to ensure contracts are valid
 */

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

// Test OpenAPI file exists and is valid YAML/JSON parseable
test('OpenAPI specification exists and is readable', () => {
  const openApiPath = path.join(__dirname, '../openapi/arinar-v1.yaml');
  assert.ok(fs.existsSync(openApiPath), 'OpenAPI file should exist');
  
  const content = fs.readFileSync(openApiPath, 'utf8');
  assert.ok(content.length > 0, 'OpenAPI file should not be empty');
  assert.ok(content.includes('openapi:'), 'Should contain openapi version');
  assert.ok(content.includes('info:'), 'Should contain info section');
  assert.ok(content.includes('paths:'), 'Should contain paths section');
});

// Test required endpoints are defined
test('OpenAPI contains all required endpoints', () => {
  const openApiPath = path.join(__dirname, '../openapi/arinar-v1.yaml');
  const content = fs.readFileSync(openApiPath, 'utf8');
  
  const requiredPaths = [
    '/health:',
    '/agent-templates:',
    '/agents:',
    '/debates:',
    '/debates/{debate_id}:',
    '/debates/run:',
    '/debates/setup:',
    '/debates/{debate_id}/participants:',
    '/debates/{debate_id}/start:',
    '/debates/{debate_id}/pause:',
    '/debates/{debate_id}/resume:',
    '/debates/{debate_id}/intervene:',
    '/debates/{debate_id}/end:',
    '/debates/{debate_id}/events:',
    '/debates/{debate_id}/events/stream:',
    '/debates/{debate_id}/summarize:',
    '/debates/{debate_id}/summary:',
    '/openrouter/models:',
    '/openrouter/account:',
    '/personas/generate-draft:',
    '/personas/validate:',
    '/workspaces/{workspace_id}/memory/importable:',
    '/debates/{debate_id}/memory/preview:',
    '/debates/{debate_id}/memory/import:',
    '/debates/{debate_id}/memory/grants:',
    '/debates/{debate_id}/memory/grants/{grant_id}:',
    '/debates/{debate_id}/preflight/start:',
    '/debates/{debate_id}/preflight/status:',
    '/debates/{debate_id}/preflight/retry:',
    '/debates/{debate_id}/preflight/skip:',
    '/debates/{debate_id}/artifact/init:',
    '/debates/{debate_id}/artifact:',
    '/debates/{debate_id}/artifact/sections/{section_id}/events:',
    '/debates/{debate_id}/artifact/events:',
    '/debates/{debate_id}/materials/{material_id}/embed:',
    '/debates/{debate_id}/materials/{material_id}/embed/status:',
    '/debates/{debate_id}/materials/{material_id}/ocr:',
    '/debates/{debate_id}/materials/{material_id}/ocr/status:',
    '/workspaces/{workspace_id}/settings/models:'
  ];
  
  for (const path of requiredPaths) {
    assert.ok(
      content.includes(path),
      `OpenAPI should define ${path}`
    );
  }
});

// Test event schemas exist
test('All required event schemas exist', () => {
  const schemasDir = path.join(__dirname, '../schemas/events');
  assert.ok(fs.existsSync(schemasDir), 'Event schemas directory should exist');
  
  const requiredSchemas = [
    'base-event.schema.json',
    'agent-message.schema.json',
    'debate-summary.schema.json',
    'intervention.schema.json',
    'pre-turn-nudge.schema.json',
    'research-request.schema.json',
    'research-result.schema.json',
    'research-denied.schema.json',
    'tool-call-request.schema.json',
    'tool-call-result.schema.json',
    'tool-call-denied.schema.json',
    'knowledge-imported.schema.json',
    'knowledge-rejected.schema.json',
    'unknown-response.schema.json',
    'voice-transcript-partial.schema.json',
    'voice-transcript-final.schema.json'
  ];
  
  for (const schemaFile of requiredSchemas) {
    const schemaPath = path.join(schemasDir, schemaFile);
    assert.ok(
      fs.existsSync(schemaPath),
      `Event schema ${schemaFile} should exist`
    );
    
    // Verify it's valid JSON
    const content = fs.readFileSync(schemaPath, 'utf8');
    assert.doesNotThrow(
      () => JSON.parse(content),
      `${schemaFile} should be valid JSON`
    );
  }
});

// Test event schemas are valid JSON Schema
test('Event schemas contain required JSON Schema properties', () => {
  const schemasDir = path.join(__dirname, '../schemas/events');
  const schemaFiles = fs.readdirSync(schemasDir).filter(f => f.endsWith('.schema.json'));
  
  for (const file of schemaFiles) {
    const content = fs.readFileSync(path.join(schemasDir, file), 'utf8');
    const schema = JSON.parse(content);
    
    assert.ok(schema.$schema, `${file} should have $schema property`);
    assert.ok(schema.$id, `${file} should have $id property`);
    assert.ok(schema.title, `${file} should have title property`);
    assert.ok(schema.description, `${file} should have description property`);
  }
});

// Test generated types directory exists
test('Generated types directory exists', () => {
  const generatedDir = path.join(__dirname, '../src/generated');
  assert.ok(fs.existsSync(generatedDir), 'Generated types directory should exist');
  
  const indexPath = path.join(generatedDir, 'index.ts');
  assert.ok(fs.existsSync(indexPath), 'Index file should exist');
  
  const eventTypesPath = path.join(generatedDir, 'event-types.ts');
  assert.ok(fs.existsSync(eventTypesPath), 'Event types file should exist');
});

// Test OpenAPI mentions OpenRouter, not OpenAI provider
test('OpenAPI documentation references OpenRouter policy', () => {
  const openApiPath = path.join(__dirname, '../openapi/arinar-v1.yaml');
  const content = fs.readFileSync(openApiPath, 'utf8');
  
  assert.ok(
    content.includes('OpenRouter'),
    'OpenAPI should reference OpenRouter policy'
  );
  
  // Ensure we're not directly referencing OpenAI as a provider
  // Note: "openapi:" is the spec format and is expected
  assert.ok(
    !content.includes('openai.com'),
    'Should not reference openai.com provider'
  );
  
  assert.ok(
    !content.includes('api.openai'),
    'Should not reference OpenAI API directly'
  );
});

// Test event types include all required types from ticket
test('Event schemas include all required event types', () => {
  const requiredEventTypes = [
    'agent_message',
    'intervention',
    'debate_summary',
    'pre_turn_nudge',
    'research_request',
    'research_result',
    'research_denied',
    'tool_call_request',
    'tool_call_result',
    'tool_call_denied',
    'knowledge_imported',
    'knowledge_rejected',
    'unknown_response',
    'voice_transcript_partial',
    'voice_transcript_final'
  ];
  
  const schemasDir = path.join(__dirname, '../schemas/events');
  const foundTypes = new Set();
  
  const schemaFiles = fs.readdirSync(schemasDir).filter(f => f.endsWith('.schema.json'));
  for (const file of schemaFiles) {
    const content = fs.readFileSync(path.join(schemasDir, file), 'utf8');
    const schema = JSON.parse(content);
    
    if (schema.allOf) {
      const eventTypeConst = schema.allOf.find(
        item => item.properties?.event_type?.const
      );
      if (eventTypeConst) {
        foundTypes.add(eventTypeConst.properties.event_type.const);
      }
    }
  }
  
  for (const eventType of requiredEventTypes) {
    assert.ok(
      foundTypes.has(eventType),
      `Event type ${eventType} should have a schema`
    );
  }
});

// Test schemas use UUID format for IDs
test('Schemas use UUID v4 format for identifiers', () => {
  const openApiPath = path.join(__dirname, '../openapi/arinar-v1.yaml');
  const content = fs.readFileSync(openApiPath, 'utf8');
  
  assert.ok(
    content.includes('format: uuid'),
    'OpenAPI should use UUID format for IDs'
  );
});

// Test schemas use ISO-8601 timestamps
test('Schemas use ISO-8601 date-time format for timestamps', () => {
  const openApiPath = path.join(__dirname, '../openapi/arinar-v1.yaml');
  const content = fs.readFileSync(openApiPath, 'utf8');
  
  assert.ok(
    content.includes('format: date-time'),
    'OpenAPI should use date-time format for timestamps'
  );
  
  assert.ok(
    content.includes('created_at'),
    'OpenAPI should include created_at timestamps'
  );
});
