'use client';

import { useState, useEffect } from 'react';
import styles from './AgendaPanel.module.css';

interface AgendaItem {
  id: string;
  text: string;
  timeboxMinutes?: number;
}

interface OutcomeData {
  desired: string;
  criteria: string[];
}

interface AgendaPanelProps {
  debateId: string;
}

export default function AgendaPanel({ debateId }: AgendaPanelProps) {
  const [agendaItems, setAgendaItems] = useState<AgendaItem[]>([]);
  const [outcomeData, setOutcomeData] = useState<OutcomeData>({
    desired: '',
    criteria: [],
  });
  const [newItemText, setNewItemText] = useState('');
  const [newCriterion, setNewCriterion] = useState('');

  const storageKey = `agenda_${debateId}`;
  const outcomeKey = `outcome_${debateId}`;

  useEffect(() => {
    // Load from localStorage
    const stored = localStorage.getItem(storageKey);
    const storedOutcome = localStorage.getItem(outcomeKey);
    
    if (stored) {
      try {
        setAgendaItems(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse stored agenda');
      }
    }

    if (storedOutcome) {
      try {
        setOutcomeData(JSON.parse(storedOutcome));
      } catch (e) {
        console.error('Failed to parse stored outcome');
      }
    }
  }, [debateId, storageKey, outcomeKey]);

  const saveAgenda = (items: AgendaItem[]) => {
    localStorage.setItem(storageKey, JSON.stringify(items));
    setAgendaItems(items);
  };

  const saveOutcome = (data: OutcomeData) => {
    localStorage.setItem(outcomeKey, JSON.stringify(data));
    setOutcomeData(data);
  };

  const addAgendaItem = () => {
    if (!newItemText.trim()) return;
    
    const newItem: AgendaItem = {
      id: Date.now().toString(),
      text: newItemText,
    };
    
    saveAgenda([...agendaItems, newItem]);
    setNewItemText('');
  };

  const removeAgendaItem = (id: string) => {
    saveAgenda(agendaItems.filter((item) => item.id !== id));
  };

  const addCriterion = () => {
    if (!newCriterion.trim()) return;
    
    saveOutcome({
      ...outcomeData,
      criteria: [...outcomeData.criteria, newCriterion],
    });
    setNewCriterion('');
  };

  const removeCriterion = (index: number) => {
    saveOutcome({
      ...outcomeData,
      criteria: outcomeData.criteria.filter((_, i) => i !== index),
    });
  };

  return (
    <div className={styles.panel}>
      <h3>Agenda & Outcome</h3>

      <section className={styles.section}>
        <h4>Meeting Agenda</h4>
        <div className={styles.itemsList}>
          {agendaItems.map((item, index) => (
            <div key={item.id} className={styles.agendaItem}>
              <span className={styles.itemNumber}>{index + 1}.</span>
              <span className={styles.itemText}>{item.text}</span>
              <button
                className={styles.removeBtn}
                onClick={() => removeAgendaItem(item.id)}
              >
                ✕
              </button>
            </div>
          ))}
          
          {agendaItems.length === 0 && (
            <p className={styles.empty}>No agenda items yet</p>
          )}
        </div>

        <div className={styles.addItem}>
          <input
            type="text"
            value={newItemText}
            onChange={(e) => setNewItemText(e.target.value)}
            placeholder="Add agenda item..."
            onKeyPress={(e) => e.key === 'Enter' && addAgendaItem()}
          />
          <button onClick={addAgendaItem}>Add</button>
        </div>
      </section>

      <section className={styles.section}>
        <h4>Intended Outcome</h4>
        
        <label className={styles.label}>
          What outcome do we want?
          <textarea
            value={outcomeData.desired}
            onChange={(e) => saveOutcome({ ...outcomeData, desired: e.target.value })}
            placeholder="E.g., A clear decision on product strategy..."
            rows={3}
          />
        </label>

        <label className={styles.label}>
          Success Criteria (1-3)
        </label>
        
        <div className={styles.itemsList}>
          {outcomeData.criteria.map((criterion, index) => (
            <div key={index} className={styles.criteriaItem}>
              <span className={styles.bullet}>•</span>
              <span className={styles.itemText}>{criterion}</span>
              <button
                className={styles.removeBtn}
                onClick={() => removeCriterion(index)}
              >
                ✕
              </button>
            </div>
          ))}
          
          {outcomeData.criteria.length === 0 && (
            <p className={styles.empty}>No criteria defined</p>
          )}
        </div>

        <div className={styles.addItem}>
          <input
            type="text"
            value={newCriterion}
            onChange={(e) => setNewCriterion(e.target.value)}
            placeholder="Add success criterion..."
            onKeyPress={(e) => e.key === 'Enter' && addCriterion()}
          />
          <button onClick={addCriterion}>Add</button>
        </div>
      </section>

      <p className={styles.hint}>
        💾 Saved locally for this debate (browser storage only)
      </p>
    </div>
  );
}
