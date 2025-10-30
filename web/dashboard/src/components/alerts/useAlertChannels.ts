import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { emptyChannelState, parseTargetsInput, type ChannelConfigState, type ChannelState } from "./channelForm";

type UseAlertChannelsArgs = {
  initialState: ChannelState;
  validateChannel: (channel: string, state: ChannelConfigState) => boolean;
  clearChannel: (channel: string) => void;
};

type UseAlertChannelsResult = {
  channels: ChannelState;
  replaceAll: (nextState: ChannelState) => void;
  toggleChannel: (channel: string, enabled: boolean) => void;
  updateTarget: (channel: string, value: string) => void;
  updateMetadata: (channel: string, key: string, value: string) => void;
  updateTemplate: (channel: string, template: string) => void;
};

const cloneChannelState = (state: ChannelState): ChannelState =>
  Object.fromEntries(
    Object.entries(state).map(([channel, config]) => [
      channel,
      {
        ...config,
        targets: [...config.targets],
        metadata: { ...config.metadata },
      },
    ]),
  );

export const useAlertChannels = ({ initialState, validateChannel, clearChannel }: UseAlertChannelsArgs): UseAlertChannelsResult => {
  const [channels, setChannels] = useState<ChannelState>(() => cloneChannelState(initialState));
  const initialRef = useRef(initialState);

  useEffect(() => {
    if (initialRef.current === initialState) {
      return;
    }
    initialRef.current = initialState;
    setChannels(cloneChannelState(initialState));
  }, [initialState]);

  const replaceAll = useCallback((nextState: ChannelState) => {
    initialRef.current = nextState;
    setChannels(cloneChannelState(nextState));
  }, []);

  const applyUpdate = useCallback(
    (channel: string, updater: (prev: ChannelConfigState) => ChannelConfigState) => {
      setChannels((prev) => {
        const previous = prev[channel] ?? emptyChannelState();
        const nextState = updater(previous);
        const nextChannels = {
          ...prev,
          [channel]: nextState,
        };
        if (nextState.enabled) {
          validateChannel(channel, nextState);
        } else {
          clearChannel(channel);
        }
        return nextChannels;
      });
    },
    [clearChannel, validateChannel],
  );

  const toggleChannel = useCallback(
    (channel: string, enabled: boolean) => {
      applyUpdate(channel, (prevState) => ({
        ...prevState,
        enabled,
      }));
    },
    [applyUpdate],
  );

  const updateTarget = useCallback(
    (channel: string, value: string) => {
      applyUpdate(channel, (prevState) => ({
        ...prevState,
        input: value,
        targets: parseTargetsInput(value),
      }));
    },
    [applyUpdate],
  );

  const updateMetadata = useCallback(
    (channel: string, key: string, value: string) => {
      applyUpdate(channel, (prevState) => ({
        ...prevState,
        metadata: {
          ...prevState.metadata,
          [key]: value,
        },
      }));
    },
    [applyUpdate],
  );

  const updateTemplate = useCallback(
    (channel: string, template: string) => {
      applyUpdate(channel, (prevState) => {
        if (prevState.template === template) {
          return prevState;
        }
        return {
          ...prevState,
          template,
          metadata: {},
        };
      });
    },
    [applyUpdate],
  );

  return useMemo(
    () => ({
      channels,
      replaceAll,
      toggleChannel,
      updateTarget,
      updateMetadata,
      updateTemplate,
    }),
    [channels, replaceAll, toggleChannel, updateTarget, updateMetadata, updateTemplate],
  );
};

export const cloneChannels = cloneChannelState;

