import { useCallback, useMemo, useState } from "react";
import type {
  AlertChannelType,
  AlertChannelRuleDescriptor,
  AlertChannelValidationDefinition,
} from "@/lib/alertsApi";
import { useAlertChannelSchema } from "@/hooks/useAlerts";
import type { ChannelConfigState, ChannelState } from "./channelForm";

export type ChannelValidationError = {
  targets?: string;
  metadata?: Record<string, string>;
};

type ChannelErrors = Record<string, ChannelValidationError>;

export type ChannelDefinitionMap = Partial<Record<AlertChannelType, AlertChannelValidationDefinition>>;

const hasValidationError = (error: ChannelValidationError | null): error is ChannelValidationError => {
  if (!error) {
    return false;
  }
  if (error.targets) {
    return true;
  }
  if (error.metadata && Object.keys(error.metadata).length > 0) {
    return true;
  }
  return false;
};

const formatMessage = (message: string, invalidItems: string[]) => {
  if (invalidItems.length === 0) {
    return message;
  }
  if (message.includes("{invalid}")) {
    return message.replace("{invalid}", invalidItems.join(", "));
  }
  return message;
};

const buildRegex = (rule: AlertChannelRuleDescriptor) => {
  if (!rule.pattern) {
    return null;
  }
  try {
    return new RegExp(rule.pattern, rule.flags ?? "");
  } catch (error) {
    return null;
  }
};

const applyTargetRules = (
  definition: AlertChannelValidationDefinition | undefined,
  state: ChannelConfigState,
): string | undefined => {
  if (!definition || !state.enabled) {
    return undefined;
  }
  const targets = state.targets ?? [];
  for (const rule of definition.targetRules ?? []) {
    const ruleType = rule.type;
    if (ruleType === "required") {
      if (targets.length === 0) {
        return rule.message;
      }
      continue;
    }
    if (targets.length === 0) {
      continue;
    }
    if (ruleType === "regex") {
      const regex = buildRegex(rule);
      if (!regex) {
        continue;
      }
      const invalid = targets.filter((target) => !regex.test(target));
      if (invalid.length > 0) {
        const list = rule.collectInvalid ? invalid : invalid.slice(0, 1);
        return formatMessage(rule.message, list);
      }
    } else if (ruleType === "min_length") {
      const minLength = rule.value ?? 0;
      const invalid = targets.filter((target) => target.trim().length < minLength);
      if (invalid.length > 0) {
        const list = rule.collectInvalid ? invalid : invalid.slice(0, 1);
        return formatMessage(rule.message, list);
      }
    } else if (ruleType === "enum") {
      const allowed = new Set(rule.values ?? []);
      const invalid = targets.filter((target) => !allowed.has(target));
      if (invalid.length > 0) {
        const list = rule.collectInvalid ? invalid : invalid.slice(0, 1);
        return formatMessage(rule.message, list);
      }
    }
  }
  return undefined;
};

const applyMetadataRules = (
  definition: AlertChannelValidationDefinition | undefined,
  state: ChannelConfigState,
): Record<string, string> | undefined => {
  if (!definition || !state.enabled) {
    return undefined;
  }
  const metadata = state.metadata ?? {};
  const errors: Record<string, string> = {};
  Object.entries(definition.metadataRules ?? {}).forEach(([key, rules]) => {
    const rawValue = metadata[key];
    const value = typeof rawValue === "string" ? rawValue.trim() : rawValue;
    const isEmpty = value === undefined || value === null || value === "";
    for (const rule of rules ?? []) {
      const ruleType = rule.type;
      if (ruleType === "required") {
        if (isEmpty) {
          errors[key] = rule.message;
          break;
        }
        continue;
      }
      if (isEmpty && (rule.optional ?? false)) {
        break;
      }
      if (ruleType === "min_length") {
        const minLength = rule.value ?? 0;
        if (typeof value !== "string" || value.length < minLength) {
          errors[key] = rule.message;
          break;
        }
      } else if (ruleType === "regex") {
        const regex = buildRegex(rule);
        if (!regex || typeof value !== "string") {
          continue;
        }
        if (!regex.test(value)) {
          errors[key] = formatMessage(rule.message, [value]);
          break;
        }
      } else if (ruleType === "enum") {
        const allowed = new Set(rule.values ?? []);
        if (!allowed.has(String(value))) {
          errors[key] = rule.message;
          break;
        }
      }
    }
  });
  return Object.keys(errors).length > 0 ? errors : undefined;
};

const runValidation = (
  channelType: string,
  state: ChannelConfigState,
  definitions: ChannelDefinitionMap,
): ChannelValidationError | null => {
  if (!state.enabled) {
    return null;
  }
  const definition = definitions[channelType as AlertChannelType];
  if (!definition) {
    return null;
  }
  const targetsError = applyTargetRules(definition, state);
  const metadataError = applyMetadataRules(definition, state);
  const error: ChannelValidationError = {};
  if (targetsError) {
    error.targets = targetsError;
  }
  if (metadataError) {
    error.metadata = metadataError;
  }
  return hasValidationError(error) ? error : null;
};

export const useChannelValidation = () => {
  const [errors, setErrors] = useState<ChannelErrors>({});
  const { data: schema } = useAlertChannelSchema();
  const definitions = useMemo<ChannelDefinitionMap>(() => {
    if (!schema?.channels) {
      return {};
    }
    return schema.channels.reduce<ChannelDefinitionMap>((acc, definition) => {
      acc[definition.type] = definition;
      return acc;
    }, {});
  }, [schema]);

  const setChannelError = useCallback((channelType: string, error: ChannelValidationError | null) => {
    setErrors((prev) => {
      if (!hasValidationError(error)) {
        if (!(channelType in prev)) {
          return prev;
        }
        const next = { ...prev };
        delete next[channelType];
        return next;
      }
      return {
        ...prev,
        [channelType]: error,
      };
    });
  }, []);

  const validateChannel = useCallback(
    (channelType: string, state: ChannelConfigState) => {
      const result = runValidation(channelType, state, definitions);
      setChannelError(channelType, result);
      return !hasValidationError(result);
    },
    [definitions, setChannelError],
  );

  const validateAll = useCallback(
    (channelState: ChannelState) => {
      const nextErrors: ChannelErrors = {};
      let hasErrors = false;
      Object.entries(channelState).forEach(([channelType, state]) => {
        if (!state) {
          return;
        }
        const result = runValidation(channelType, state, definitions);
        if (hasValidationError(result)) {
          hasErrors = true;
          nextErrors[channelType] = result!;
        }
      });
      setErrors(nextErrors);
      return !hasErrors;
    },
    [definitions],
  );

  const clearChannel = useCallback((channelType: string) => {
    setErrors((prev) => {
      if (!(channelType in prev)) {
        return prev;
      }
      const next = { ...prev };
      delete next[channelType];
      return next;
    });
  }, []);

  const resetErrors = useCallback(() => {
    setErrors({});
  }, []);

  return {
    errors,
    validateChannel,
    validateAll,
    clearChannel,
    resetErrors,
    definitions,
  };
};
