export function toast(message, type = 'info') {
  window.dispatchEvent(
    new CustomEvent('newshub:toast', {
      detail: { id: `${Date.now()}-${Math.random()}`, message, type },
    })
  );
}
