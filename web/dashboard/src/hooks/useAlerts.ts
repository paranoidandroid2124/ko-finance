"use client";

export const useAlerts = () => ({
  alerts: [],
  loading: false,
  refresh: () => {},
});

export const useAlertRules = () => ({
  data: { plan: null },
  isLoading: false,
  isError: false,
  refresh: () => {},
});

export default useAlerts;
