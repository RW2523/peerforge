/**
 * Setup wizard step indicator
 */

import styles from './SetupSteps.module.css';

interface Step {
  id: number;
  label: string;
}

interface SetupStepperProps {
  steps: Step[];
  currentStep: number;
}

export function SetupStepper({ steps, currentStep }: SetupStepperProps) {
  return (
    <div className={styles.steps}>
      {steps.map((stepItem) => {
        const isActive = currentStep === stepItem.id;
        const isCompleted = currentStep > stepItem.id;
        
        return (
          <div
            key={stepItem.id}
            className={`${styles.step} ${isActive ? styles.stepActive : ''} ${isCompleted ? styles.stepCompleted : ''}`}
          >
            <div className={styles.stepNumber}>
              {isCompleted ? '✓' : stepItem.id}
            </div>
            <div className={styles.stepLabel}>{stepItem.label}</div>
          </div>
        );
      })}
    </div>
  );
}
