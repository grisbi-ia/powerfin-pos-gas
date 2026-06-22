// Simple toast utility — wraps window.alert for now
// Replace with a proper toast library when needed

type ToastType = 'success' | 'error' | 'info';

function showToast(message: string, type: ToastType = 'info') {
  const bg = type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#3b82f6';
  const div = document.createElement('div');
  div.className = 'fixed bottom-4 right-4 z-50 px-4 py-3 rounded-lg text-white text-sm font-medium shadow-lg transition-all';
  div.style.cssText = `background:${bg};max-width:24rem;animation:slideIn 0.3s ease-out`;
  div.textContent = message;
  document.body.appendChild(div);
  setTimeout(() => {
    div.style.opacity = '0';
    setTimeout(() => div.remove(), 300);
  }, 3000);
}

// Add CSS animation
if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = '@keyframes slideIn { from { transform: translateY(1rem); opacity:0 } to { transform:translateY(0); opacity:1 } }';
  document.head.appendChild(style);
}

export const toast = {
  success: (msg: string) => showToast(msg, 'success'),
  error: (msg: string) => showToast(msg, 'error'),
  info: (msg: string) => showToast(msg, 'info'),
};
