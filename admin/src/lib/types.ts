export interface PaginatedResponse<T = any> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface DashboardSummary {
  total_sales: number;
  dispatch_count: number;
  avg_ticket: number;
  cash_collected: number;
  non_cash_collected: number;
  active_shifts: number;
  date_from: string;
  date_to: string;
}

export interface UserListItem {
  user_id: number;
  username: string;
  name: string;
  role: string;
  role_name: string;
  is_active: boolean;
}

export interface UserDetail {
  user_id: number;
  username: string;
  name: string;
  role_id: number;
  role: string;
  role_name: string;
  accounting_cash_code: string | null;
  is_active: boolean;
}

export interface RoleOption {
  role_id: number;
  code: string;
  name: string;
}
