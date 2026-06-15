import * as api from '@/lib/api';
import styles from './SetupSteps.module.css';

interface ReviewStepProps {
  title: string;
  problemStatement: string;
  timeboxMinutes?: number;
  yoloMode?: boolean;
  autoTurnDelay?: number;
  materials: api.SetupMaterial[];
  participants: api.SetupParticipant[];
  workspaceId: string;
}

export function ReviewStep({
  title,
  problemStatement,
  timeboxMinutes,
  yoloMode,
  autoTurnDelay,
  materials,
  participants,
  workspaceId,
}: ReviewStepProps) {
  return (
    <div className={styles.section}>
      <h2>Review & Launch</h2>
      
      <div className={styles.reviewCard}>
        <h3>Meeting Details</h3>
        <div className={styles.reviewItem}>
          <strong>Title:</strong> {title}
        </div>
        <div className={styles.reviewItem}>
          <strong>Problem:</strong> {problemStatement}
        </div>
        <div className={styles.reviewItem}>
          <strong>Timebox:</strong> {timeboxMinutes ? `${timeboxMinutes} minutes` : 'None'}
        </div>
        {yoloMode && (
          <div className={styles.reviewItem} style={{ color: '#fb923c', fontWeight: 600 }}>
            <strong>🚀 YOLO Mode:</strong> Enabled (auto-turn every {autoTurnDelay}s)
          </div>
        )}
        <div className={styles.reviewItem}>
          <strong>Materials:</strong> {materials.length}
        </div>
        <div className={styles.reviewItem}>
          <strong>Participants:</strong> {participants.length}
        </div>
      </div>

      <div className={styles.reviewCard}>
        <h3>Request Preview</h3>
        <pre className={styles.jsonPreview}>
          {JSON.stringify({
            workspace_id: workspaceId,
            title,
            problem_statement: problemStatement,
            timebox_minutes: timeboxMinutes,
            participants,
            materials,
          }, null, 2)}
        </pre>
      </div>
    </div>
  );
}
