import { SETUP_LIMITS } from '@/lib/setupValidation';
import styles from './SetupSteps.module.css';

interface EditableListItemProps {
  item: string;
  isEditing: boolean;
  editValue: string;
  editError: string;
  disabled?: boolean;
  onStartEdit: () => void;
  onEditValueChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
  onRemove: () => void;
}

export function EditableListItem({
  item,
  isEditing,
  editValue,
  editError,
  disabled = false,
  onStartEdit,
  onEditValueChange,
  onSave,
  onCancel,
  onRemove,
}: EditableListItemProps) {
  if (isEditing) {
    return (
      <li className={styles.itemListEditing}>
        <div className={styles.itemEditForm}>
          <input
            type="text"
            value={editValue}
            onChange={(e) => onEditValueChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                onSave();
              } else if (e.key === 'Escape') {
                e.preventDefault();
                onCancel();
              }
            }}
            maxLength={SETUP_LIMITS.ITEM_MAX}
            disabled={disabled}
            autoFocus
            aria-invalid={!!editError}
            className={styles.itemEditInput}
          />
          {editError && <span className={styles.fieldError}>{editError}</span>}
          <div className={styles.itemEditActions}>
            <button
              type="button"
              onClick={onSave}
              disabled={disabled}
              className={styles.itemEditSave}
            >
              Save
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={disabled}
              className={styles.itemEditCancel}
            >
              Cancel
            </button>
          </div>
        </div>
      </li>
    );
  }

  return (
    <li>
      <span>{item}</span>
      <div className={styles.itemListActions}>
        <button
          type="button"
          onClick={onStartEdit}
          className={styles.editButton}
          disabled={disabled}
          title="Edit item"
          aria-label="Edit item"
        >
          ✎
        </button>
        <button
          type="button"
          onClick={onRemove}
          className={styles.removeButton}
          disabled={disabled}
          title="Remove item"
          aria-label="Remove item"
        >
          ✕
        </button>
      </div>
    </li>
  );
}
