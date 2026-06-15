#!/usr/bin/env python3
"""
Real-time SSE Monitor with Frontend Filtering Simulation
Shows exactly what the frontend SHOULD display
"""
import requests
import json
import sys
from datetime import datetime

debate_id = 'ff97d8d1-c9e3-4c0e-b347-9a9bdb88c489'
url = f'http://localhost:8000/debates/{debate_id}/events/stream'

# Frontend filter list (from EventFeed.tsx)
FILTERED_TYPES = ['keepalive', 'heartbeat', 'presence_update', 'typing', 'system_message']

print("=" * 80)
print("SSE STREAM MONITOR - Frontend Simulation")
print("=" * 80)
print(f"Debate ID: {debate_id}")
print(f"URL: {url}")
print(f"Time: {datetime.now().isoformat()}")
print("=" * 80)
print()

try:
    response = requests.get(
        url,
        headers={
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache'
        },
        stream=True,
        timeout=60
    )
    
    if response.status_code != 200:
        print(f"❌ ERROR: HTTP {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    print("✅ Connected to SSE stream")
    print()
    print("=" * 80)
    print("EVENTS (showing what frontend SHOULD display)")
    print("=" * 80)
    print()
    
    event_count = 0
    displayed_count = 0
    filtered_count = 0
    current_event = {}
    
    for line in response.iter_lines(decode_unicode=True):
        if not line or line.strip() == '':
            # End of event
            if current_event and 'data' in current_event:
                event_count += 1
                
                try:
                    data = json.loads(current_event['data'])
                    event_type = data.get('event_type')
                    
                    # Apply frontend filtering
                    should_filter = event_type in FILTERED_TYPES
                    
                    if should_filter:
                        filtered_count += 1
                        print(f"[Event #{event_count}] FILTERED OUT: {event_type}")
                        print(f"  Reason: In filter list")
                        print()
                    else:
                        displayed_count += 1
                        actor = data.get('payload', {}).get('agent_name') or \
                                data.get('payload', {}).get('actor') or \
                                'System'
                        
                        message = data.get('payload', {}).get('message') or \
                                  data.get('payload', {}).get('content') or \
                                  data.get('payload', {}).get('text') or \
                                  '(no message)'
                        
                        print(f"[Event #{event_count}] ✅ DISPLAYED")
                        print(f"  SSE Event Type: {current_event.get('event_type', 'message')}")
                        print(f"  Event Type: {event_type or 'UNKNOWN'}")
                        print(f"  Actor: {actor}")
                        print(f"  Message: {message[:100]}{'...' if len(message) > 100 else ''}")
                        print(f"  Event ID: {data.get('event_id', 'N/A')}")
                        print(f"  Sequence: {data.get('sequence_number', 'N/A')}")
                        
                        # Check for potential "System UNKNOWN" display
                        if actor == 'System' and not event_type:
                            print(f"  ⚠️  WARNING: This would show as 'System UNKNOWN' in UI!")
                        
                        print()
                
                except json.JSONDecodeError as e:
                    print(f"[Event #{event_count}] ❌ JSON PARSE ERROR")
                    print(f"  Error: {e}")
                    print(f"  Data: {current_event.get('data', '')[:200]}")
                    print()
                
                current_event = {}
            continue
        
        if line.startswith(':'):
            # Keepalive comment
            continue
        
        # Parse SSE field
        if ':' in line:
            field, _, value = line.partition(':')
            value = value.lstrip()
            
            if field == 'event':
                current_event['event_type'] = value
            elif field == 'data':
                current_event['data'] = value
            elif field == 'id':
                current_event['id'] = value
        
        # Stop after 100 events
        if event_count >= 100:
            print("=" * 80)
            print(f"Stopped after {event_count} events")
            break
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total events received: {event_count}")
    print(f"Events displayed in UI: {displayed_count}")
    print(f"Events filtered out: {filtered_count}")
    print()
    print("Expected for this debate:")
    print("  - 2 agent_message events (displayed)")
    print("  - 3 system_message events (filtered)")
    print("  - 1 presence_update event (filtered)")
    print("  - 1 state_update event (displayed)")
    print("  - 1 stream_end event (displayed)")
    print()
    
    if displayed_count > 4:
        print("⚠️  WARNING: More events displayed than expected!")
        print("   This could explain the spam issue.")
    elif displayed_count < 4:
        print("ℹ️  Fewer events than expected. Stream may have ended early.")
    else:
        print("✅ Event count matches expectations")
    
except requests.exceptions.RequestException as e:
    print(f"❌ CONNECTION ERROR: {e}")
    sys.exit(1)
except KeyboardInterrupt:
    print("\n\n⏹️  Stopped by user")
    sys.exit(0)
