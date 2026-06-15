#!/usr/bin/env python3
"""
Test script to verify agent thinking feature works
Run this to trigger a turn and see thinking in database + logs
"""
import sys
import os

# Add API directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/api/src'))

from turn_orchestrator import TurnOrchestrator
from database import get_db_connection, get_cursor

def main():
    # Get API key
    api_key = input("Enter your OpenRouter API key (or press Enter to skip): ").strip()
    
    if not api_key:
        print("❌ API key required to test thinking feature")
        print("\nTo test without API key, check existing events:")
        print("  python3 -c 'from database import *; ...'")
        return
    
    debate_id = '011fe524-af70-4519-84b3-0ba99046479c'
    
    print(f"\n🎯 Testing thinking feature for debate {debate_id}")
    print("=" * 60)
    
    # Check before counts
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute("SELECT COUNT(*) as count FROM events WHERE event_type = 'agent_thinking'")
        before_count = cursor.fetchone()['count']
        print(f"\n📊 Thinking events BEFORE: {before_count}")
    
    # Trigger turn with thinking
    print("\n🚀 Triggering next turn...")
    print("   (Watch for 🧠 📡 emojis in output)\n")
    
    orchestrator = TurnOrchestrator(api_key)
    result = orchestrator.trigger_next_turn(debate_id)
    
    print(f"\n✅ Turn complete!")
    print(f"   Agent: {result.get('agent_name')}")
    print(f"   Message: {result.get('message', '')[:100]}...")
    
    # Check after counts
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute("SELECT COUNT(*) as count FROM events WHERE event_type = 'agent_thinking'")
        after_count = cursor.fetchone()['count']
        print(f"\n📊 Thinking events AFTER: {after_count}")
        print(f"   New thinking events: {after_count - before_count}")
        
        if after_count > before_count:
            print(f"\n🎉 SUCCESS! Thinking feature is working!")
            print(f"\n   - {after_count - before_count} thinking events persisted to database")
            print(f"   - Check your browser UI for '🧠 Show thinking process' button")
            print(f"   - Refresh the page if needed: http://localhost:3000/room?debate_id={debate_id}")
        else:
            print(f"\n❌ FAILED! No thinking events were created")
            print(f"   Check logs above for errors")

if __name__ == '__main__':
    main()
