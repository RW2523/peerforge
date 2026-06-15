#!/usr/bin/env python3
"""
Test SSE stream to see what's actually being sent
"""
import requests
import json
import sys

debate_id = 'ff97d8d1-c9e3-4c0e-b347-9a9bdb88c489'
url = f'http://localhost:8000/debates/{debate_id}/events/stream'

print(f"Connecting to: {url}\n")
print("=" * 80)

try:
    # Connect without auth since REQUIRE_AUTH=false
    response = requests.get(
        url,
        headers={
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache'
        },
        stream=True,
        timeout=30
    )
    
    print(f"Response Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}\n")
    print("=" * 80)
    print("STREAMING EVENTS:\n")
    
    line_count = 0
    event_count = 0
    current_event = {}
    
    for line in response.iter_lines(decode_unicode=True):
        line_count += 1
        
        # Print raw line
        print(f"[Line {line_count}] {repr(line)}")
        
        if not line or line.strip() == '':
            # End of event
            if current_event:
                event_count += 1
                print(f"\n>>> EVENT #{event_count} <<<")
                print(json.dumps(current_event, indent=2))
                print()
                current_event = {}
            continue
        
        if line.startswith(':'):
            # Comment/keepalive
            print(f"  (keepalive comment)")
            continue
        
        # Parse SSE field
        if ':' in line:
            field, _, value = line.partition(':')
            value = value.lstrip()
            
            if field == 'event':
                current_event['event_type'] = value
            elif field == 'data':
                try:
                    current_event['data'] = json.loads(value)
                except:
                    current_event['data'] = value
            elif field == 'id':
                current_event['id'] = value
        
        # Stop after 100 lines or 20 events
        if line_count >= 100 or event_count >= 20:
            print("\n" + "=" * 80)
            print(f"Stopped after {line_count} lines and {event_count} events")
            break
            
except requests.exceptions.RequestException as e:
    print(f"ERROR: {e}")
    sys.exit(1)
except KeyboardInterrupt:
    print("\n\nInterrupted by user")
    sys.exit(0)
