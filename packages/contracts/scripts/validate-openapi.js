#!/usr/bin/env node
/**
 * Validate OpenAPI specification
 * Ensures the API contract is valid and follows OpenAPI 3.1 spec
 */

const SwaggerParser = require('@apidevtools/swagger-parser');
const path = require('path');

const OPENAPI_PATH = path.join(__dirname, '../openapi/arinar-v1.yaml');

console.log('🔍 Validating OpenAPI specification...');
console.log(`   File: ${OPENAPI_PATH}`);

async function validate() {
  try {
    const api = await SwaggerParser.validate(OPENAPI_PATH);
    
    console.log('✅ OpenAPI specification is valid!');
    console.log(`   API Title: ${api.info.title}`);
    console.log(`   API Version: ${api.info.version}`);
    
    // Count endpoints
    const pathCount = Object.keys(api.paths || {}).length;
    let operationCount = 0;
    
    for (const path in api.paths) {
      operationCount += Object.keys(api.paths[path]).filter(
        key => ['get', 'post', 'put', 'patch', 'delete'].includes(key)
      ).length;
    }
    
    console.log(`   Paths: ${pathCount}`);
    console.log(`   Operations: ${operationCount}`);
    
    // Validate required endpoints from ticket
    const requiredEndpoints = [
      { method: 'get', path: '/health' },
      { method: 'get', path: '/agent-templates' },
      { method: 'get', path: '/agents' },
      { method: 'post', path: '/agents' },
      { method: 'get', path: '/debates' },
      { method: 'post', path: '/debates' },
      { method: 'get', path: '/debates/{debate_id}' },
      { method: 'post', path: '/debates/run' },
      { method: 'post', path: '/debates/setup' },
      { method: 'post', path: '/debates/{debate_id}/participants' },
      { method: 'post', path: '/debates/{debate_id}/start' },
      { method: 'post', path: '/debates/{debate_id}/pause' },
      { method: 'post', path: '/debates/{debate_id}/resume' },
      { method: 'post', path: '/debates/{debate_id}/intervene' },
      { method: 'post', path: '/debates/{debate_id}/end' },
      { method: 'get', path: '/debates/{debate_id}/events' },
      { method: 'get', path: '/debates/{debate_id}/events/stream' },
      { method: 'post', path: '/debates/{debate_id}/summarize' },
      { method: 'get', path: '/debates/{debate_id}/summary' },
      { method: 'get', path: '/openrouter/models' },
      { method: 'get', path: '/openrouter/account' },
      { method: 'post', path: '/personas/generate-draft' },
      { method: 'post', path: '/personas/validate' },
      { method: 'get', path: '/workspaces/{workspace_id}/memory/importable' },
      { method: 'get', path: '/debates/{debate_id}/memory/preview' },
      { method: 'post', path: '/debates/{debate_id}/memory/import' },
      { method: 'get', path: '/debates/{debate_id}/memory/grants' },
      { method: 'delete', path: '/debates/{debate_id}/memory/grants/{grant_id}' },
      { method: 'post', path: '/debates/{debate_id}/preflight/start' },
      { method: 'get', path: '/debates/{debate_id}/preflight/status' },
      { method: 'post', path: '/debates/{debate_id}/preflight/retry' },
      { method: 'post', path: '/debates/{debate_id}/preflight/skip' },
      { method: 'post', path: '/debates/{debate_id}/artifact/init' },
      { method: 'get', path: '/debates/{debate_id}/artifact' },
      { method: 'post', path: '/debates/{debate_id}/artifact/sections/{section_id}/events' },
      { method: 'get', path: '/debates/{debate_id}/artifact/events' },
      { method: 'post', path: '/debates/{debate_id}/materials/{material_id}/embed' },
      { method: 'get', path: '/debates/{debate_id}/materials/{material_id}/embed/status' },
      { method: 'post', path: '/debates/{debate_id}/materials/{material_id}/ocr' },
      { method: 'get', path: '/debates/{debate_id}/materials/{material_id}/ocr/status' },
      { method: 'get', path: '/workspaces/{workspace_id}/settings/models' },
      { method: 'put', path: '/workspaces/{workspace_id}/settings/models' }
    ];
    
    console.log('\n📋 Checking required endpoints:');
    let allPresent = true;
    
    for (const endpoint of requiredEndpoints) {
      const exists = api.paths[endpoint.path]?.[endpoint.method] !== undefined;
      const status = exists ? '✅' : '❌';
      console.log(`   ${status} ${endpoint.method.toUpperCase()} ${endpoint.path}`);
      if (!exists) allPresent = false;
    }
    
    if (!allPresent) {
      console.error('\n❌ Some required endpoints are missing!');
      process.exit(1);
    }
    
    console.log('\n✅ All required endpoints present');
    
  } catch (error) {
    console.error('\n❌ OpenAPI validation failed:');
    console.error(error.message);
    process.exit(1);
  }
}

validate();
