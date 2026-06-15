#!/usr/bin/env node
/**
 * Validate JSON Schema event definitions
 * Ensures all event schemas are valid and include required event types
 */

const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const fs = require('fs');
const path = require('path');

const SCHEMAS_DIR = path.join(__dirname, '../schemas/events');

// Required event types from ticket and realtime protocol
const REQUIRED_EVENT_TYPES = [
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

console.log('🔍 Validating event schemas...');
console.log(`   Directory: ${SCHEMAS_DIR}`);

const ajv = new Ajv({ 
  strict: false,
  allowUnionTypes: true 
});
addFormats(ajv);

let validCount = 0;
let errorCount = 0;
const foundEventTypes = new Set();

// Read all schema files
const schemaFiles = fs.readdirSync(SCHEMAS_DIR).filter(f => f.endsWith('.schema.json'));

console.log(`\n📄 Found ${schemaFiles.length} schema files`);

for (const file of schemaFiles) {
  const filePath = path.join(SCHEMAS_DIR, file);
  const schemaContent = fs.readFileSync(filePath, 'utf8');
  
  try {
    const schema = JSON.parse(schemaContent);
    
    // Basic validation
    if (!schema.$schema) {
      throw new Error('Missing $schema property');
    }
    
    // Track event types
    if (file !== 'base-event.schema.json' && schema.allOf) {
      const eventTypeConst = schema.allOf.find(
        item => item.properties?.event_type?.const
      );
      if (eventTypeConst) {
        foundEventTypes.add(eventTypeConst.properties.event_type.const);
      }
    }
    
    console.log(`   ✅ ${file}`);
    validCount++;
    
  } catch (error) {
    console.error(`   ❌ ${file}: ${error.message}`);
    errorCount++;
  }
}

// Check for required event types
console.log('\n📋 Checking required event types:');
let allPresent = true;

for (const eventType of REQUIRED_EVENT_TYPES) {
  const exists = foundEventTypes.has(eventType);
  const status = exists ? '✅' : '❌';
  console.log(`   ${status} ${eventType}`);
  if (!exists) allPresent = false;
}

console.log(`\n📊 Summary:`);
console.log(`   Valid schemas: ${validCount}`);
console.log(`   Errors: ${errorCount}`);
console.log(`   Event types defined: ${foundEventTypes.size}`);

if (errorCount > 0) {
  console.error('\n❌ Schema validation failed!');
  process.exit(1);
}

if (!allPresent) {
  console.error('\n❌ Some required event types are missing!');
  process.exit(1);
}

console.log('\n✅ All event schemas are valid!');
