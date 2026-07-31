/**
 * Helpers for making non-native controls behave like native ones.
 */
import type { KeyboardEvent } from 'react';

/**
 * Activate a custom control on Enter or Space, as a real button or radio does.
 *
 * Space is included because that is what activates a radio or button natively;
 * omitting it is the usual reason a "clickable div" feels broken to anyone not
 * using a mouse. preventDefault stops Space from scrolling the page.
 */
export function activateOnKey(e: KeyboardEvent, action: () => void): void {
  if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
    e.preventDefault();
    action();
  }
}
