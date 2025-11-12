"use client";

const parseBoolean = (value: string | undefined): boolean => value?.toLowerCase() === "true";

export const FEATURE_STARTER_ENABLED = parseBoolean(process.env.NEXT_PUBLIC_STARTER_ENABLED);
export const STARTER_CHECKOUT_URL = process.env.NEXT_PUBLIC_STARTER_CHECKOUT_URL ?? null;
