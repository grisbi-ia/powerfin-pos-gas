export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-EC', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(value);
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('es-EC', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  }).format(new Date(date));
}

export function formatDateTime(date: string | Date): string {
  return new Intl.DateTimeFormat('es-EC', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(date));
}

export function formatNumber(value: number, decimals = 0): string {
  return new Intl.NumberFormat('es-EC', {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(value);
}
