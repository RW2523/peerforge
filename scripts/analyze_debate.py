#!/usr/bin/env python3
"""
Quick script to analyze any debate from command line
Usage: python scripts/analyze_debate.py <debate_id>
"""
import sys
sys.path.insert(0, '/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api')

from src.database import get_db_connection, get_cursor


def analyze_debate(debate_id: str):
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        
        # Get debate info
        cursor.execute("SELECT * FROM debates WHERE debate_id = %s", (debate_id,))
        debate = cursor.fetchone()
        
        if not debate:
            print(f"❌ Debate {debate_id} not found")
            return
        
        print("=" * 100)
        print(f"DEBATE: {debate['title']}")
        print("=" * 100)
        
        policy = debate.get('policy_config', {})
        print(f"Max Rounds: {policy.get('max_rounds', 'N/A')}")
        print(f"Host Enabled: {policy.get('enable_host', False)}")
        
        if debate.get('desired_outcomes'):
            print(f"\n🎯 GOALS:")
            for outcome in debate['desired_outcomes']:
                print(f"  - {outcome}")
        
        # Get agent messages
        cursor.execute("""
            SELECT COUNT(*) as count FROM events
            WHERE debate_id = %s AND event_type = 'agent_message'
        """, (debate_id,))
        msg_count = cursor.fetchone()['count']
        
        # Get coalitions
        cursor.execute("""
            SELECT * FROM events
            WHERE debate_id = %s AND event_type = 'coalition_formed'
            ORDER BY sequence_number
        """, (debate_id,))
        coalitions = cursor.fetchall()
        
        # Get private messages
        cursor.execute("""
            SELECT * FROM events
            WHERE debate_id = %s AND event_type = 'private_message'
            ORDER BY sequence_number
        """, (debate_id,))
        private_msgs = cursor.fetchall()
        
        # Get host
        cursor.execute("""
            SELECT * FROM events
            WHERE debate_id = %s AND sender_type = 'host'
            ORDER BY sequence_number DESC LIMIT 1
        """, (debate_id,))
        host = cursor.fetchone()
        
        print(f"\n📊 STATS:")
        print(f"  Agent Messages: {msg_count}")
        print(f"  Coalitions: {len(coalitions)}")
        print(f"  Private Messages: {len(private_msgs)}")
        print(f"  Host Conclusion: {'Yes' if host else 'No'}")
        
        if coalitions:
            print(f"\n🤝 COALITIONS ({len(coalitions)}):")
            for c in coalitions:
                content = c['content']
                print(f"  [{c['sequence_number']}] {content.get('type', 'alliance').upper()}")
                print(f"    Members: {', '.join(content.get('members', []))}")
                print(f"    Formed by: {content.get('formed_by')}")
                if content.get('strategy'):
                    print(f"    Strategy: {content['strategy']}")
        
        if private_msgs:
            print(f"\n💬 PRIVATE MESSAGES ({len(private_msgs)}):")
            for pm in private_msgs:
                content = pm['content']
                print(f"  [{pm['sequence_number']}] {content.get('from_agent')} → {content.get('to_agent')}")
                print(f"    {content.get('message')}")
        
        cursor.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_debate.py <debate_id>")
        sys.exit(1)
    
    analyze_debate(sys.argv[1])
